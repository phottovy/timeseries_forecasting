from datetime import datetime, timedelta
import pandas as pd
from pandas import date_range, DataFrame, Panel, set_option, read_csv, read_pickle, to_datetime
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.seasonal import seasonal_decompose
from scipy.stats import shapiro
from sklearn import metrics
from datetime import datetime, timedelta



# import data
def pickles_puller(source_id, path):
    """
    Imports the prediction and provenance data.
    """
    try:
        this_prediction_panel = read_pickle(
            path + 'feed_' + str(source_id) + '_t_60_f_14_forecast.pickle')
        this_provenance_panel = read_pickle(
            path + 'feed_' + str(source_id) + '_t_60_f_14_provenance.pickle')
    except IOError as ioe:
        print('source id: "' + str(source_id) + '" not found.')
        return Panel(data=None), Panel(data=None)

    return this_prediction_panel, this_provenance_panel


# forecast methods
def moving_avg_forecast(data, roll_periods=14):
    '''
    Calculates rolling average forecast for each day.
    '''
    data['mov_avg'] = data.rolling(roll_periods).mean()
    return data


def sing_exp_forecast(train_data, test_data):
    '''
    Calculate Single Exponential Smoothing Forecast
    '''
    sing_exp = SimpleExpSmoothing(train_data)
    sing_exp_model = sing_exp.fit()
    sing_exp_df = train_data.copy()
    sing_exp_df['sing_exp'] = sing_exp_model.fittedvalues
    sing_exp_df = sing_exp_df.append(test_data)
    for date in pd.date_range('2016-09-01', '2016-10-31'):
        sing_exp_df.loc[date, 'sing_exp'] = sing_exp_model.predict(date)[0]
        sing_exp = SimpleExpSmoothing(sing_exp_df.loc[:date, 'this_data'])
        sing_exp_model = sing_exp.fit()
    return sing_exp_df

# optimized inputs
p, d, q = 14, 1, 0
P, D, Q = 14, 1, 1
s = 14


def opt_arima_forecast(train_data, test_data, results=False):
    if results:
        train_results = results
    else:
        train_model = sm.tsa.statespace.SARIMAX(
            train_data, order=(p, d, q), seasonal_order=(P, D, Q, s))
        # this model takes some time to fit
        train_results = train_model.fit()
    opt_arima_df = train_data.copy()
    opt_arima_df['opt_arima'] = train_results.fittedvalues
    opt_arima_df = opt_arima_df.append(test_data)
    opt_arima_df.loc['2016-09-01':, 'opt_arima'] = train_results.forecast(61)
    return opt_arima_df














# metrics
def get_weekly_error_for_all_days(panel, metric='RMSE'):
    '''
    Create a dataframe to compare group the results of all six forecasting methods in one dataframe
    '''
    metric = metric.upper()
    this_error_df = DataFrame(index=panel.major_axis, columns=panel.items)
    # Iterate through all tabs of panels and then the timeseries indices
    for this_tab in panel.items:
        for this_date in panel.major_axis:
            this_data_forecast = get_weekly_forecast_data(
                panel, this_tab, this_date)
            this_data_raw = get_raw_weekly(panel, this_date)
            this_error_df.loc[this_date][this_tab] = METRIC_DICT[metric](
                this_data_raw, this_data_forecast)
    this_error_df = this_error_df.infer_objects()
    return this_error_df


def get_weekly_forecast_data(panel, tab='data', starting_datetime=datetime(2016, 1, 1)):
    """
    Returns the weekly forecast data from columns columns p0:p7
    """
    # Pull in forecasts for p0:p7 for the specified tab in the Pandas panel
    wrong_indexed_forecast_data = panel.loc[tab, starting_datetime, 'p0':'p7']
    # Create a datetime index
    new_datetime_index = date_range(
        starting_datetime, starting_datetime+timedelta(days=7), freq='1d')
    # Update the forecast data with the datetime index
    correctly_indexed_forecast_data_df = DataFrame(
        wrong_indexed_forecast_data).set_index(new_datetime_index)
    # Rename the forecast column
    correctly_indexed_forecast_data_df.columns = [tab]
    # Returns a series for comparison
    correctly_indexed_forecast_data_series = correctly_indexed_forecast_data_df[tab]
    return correctly_indexed_forecast_data_series


def get_raw_weekly(panel, starting_datetime=datetime(2016, 1, 1)):
    """
    Returns actuals to be paired with forecast data from columns p0:p7 to compare actuals to forecast
    """
    # create a datetime index delta object to supply to the new index:
    #dt_delta = date_range()
    new_datetime_index = date_range(
        starting_datetime, starting_datetime + timedelta(days=7), freq='1d')
    raw_data = panel.loc['data', new_datetime_index, 'this_data']
    return raw_data




def create_weekly_error_metric_df(forecast_df, metric='RMSE'):
    '''
    Input a dataframe with the first two columns = [Actuals, Forecast]
    Calculates 7 day error for all days for the provided forecast method.
    Available metrics: RMSE, MSE, R2, MAE, MEDAE, MSLE, MAPE
    '''
    metric = metric.upper()
    forecast_df.dropna(inplace=True)
    for date in forecast_df.itertuples():
        begin, end = date[0], date[0]+timedelta(days=7)
        forecast_df.loc[begin, f'{metric}'] = METRIC_DICT[metric](
            forecast_df.loc[begin:end].iloc[:, 0], forecast_df.loc[begin:end].iloc[:, 1])
    return forecast_df


def create_metrics_df(panel, metric='RMSE'):
    '''
    Input Pandas panel
    Calculates and creates a panelframe of values to evaluate columns p0:p14 for each of the six predictors.
    Available metrics: RMSE, MSE, R2, MAE, MEDAE, MSLE, MAPE
    '''
    metric = metric.upper()
    df = pd.DataFrame(index=panel.items,
                      columns=panel.loc[panel.items[0]].columns)
    df.drop('this_data', axis=1, inplace=True)
    for idx, item in enumerate(panel.items):
        item_df = panel.loc[f'{item}'].dropna()
        for num in range(len(item_df.columns)-1):
            df.iloc[idx, num] = METRIC_DICT[metric](
                item_df['this_data'], item_df[f'p{num}'])

    df = df.infer_objects()
    df['mean'] = df.mean(axis=1)
    return df  # df.idxmin().value_counts()



def adf_results(data):
    """
    Return results of Augmented Dickey-Fuller Test
    """
    result = adfuller(data)
    print('Augmented Dickey-Fuller Test:')
    print(f'T-Statistic: {result[0]:.5f}')
    print(f'p-value: {result[1]:.5f}')
    print(f"adf-1%: {result[4]['1%']:.5f}")
    print(f"adf-5%: {result[4]['5%']:.5f}")
    print(f"adf-10%: {result[4]['10%']:.5f}")
    print(f'# Lags: {result[2]}')
    print(f'# of observations: {result[3]}')
    if result[1] <= 0.05:
        print(f'{result[1]:.5f} <= 0.05. Data is stationary')
    else:
        print(f'{result[1]:.5f} > 0.05. Data is non-stationary')


def sw_results(data):
    """
    Return results of Shapiro-Wilk Test
    """
    result = shapiro(data)
    print('Shapiro-Wilk Test:')
    print(f'T-Statistic: {result[0]:.5f}')
    print(f'p-value: {result[1]:.5f}')


def root_mean_squared_error(y_true, y_pred):
    '''
    Calculates RMSE metric
    '''
    # return np.sqrt(mean_squared_error(y_true, y_pred))
    return np.sqrt(((y_true - y_pred)) ** 2).mean()


def mean_absolute_percentage_error(y_true, y_pred):
    '''
    Calculates MAPE metric
    '''
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100







# visuals
def plot_actuals(data, savefig=False):
    '''
    Plot the raw time series data
    '''
    plt.figure()
    data.Actuals.plot()
    plt.title('Raw Data')
    plt.xlabel('Date')
    plt.legend()
    plt.tight_layout()
    if savefig:
        plt.savefig('../images/raw_data.png', dpi=72)
    plt.show()


def plot_rolling_data(data, roll_periods=14, savefig=False):
    '''
    Plot time series data with rolling mean and std.
    '''
    plt.figure()
    plt.title(f'Data with Rolling Mean')
    plt.xlabel('Date')
    plt.plot(data, label='Actuals')
    rolling_mean = data.rolling(roll_periods).mean()
    rolling_std = data.rolling(roll_periods).std()
    plt.plot(rolling_mean, alpha=0.6,
             label=f'{roll_periods} Period Rolling Mean')
    plt.plot(rolling_std, alpha=0.6,
             label=f'{roll_periods} Period Rolling STD')
    plt.legend()
    plt.tight_layout()
    if savefig:
        plt.savefig('../images/rolling_mean.png', dpi=72)
    plt.show()


def day_of_week_plot(data, view='quarter', savefig=False):
    '''
    Creates a bar plot with different colors for weekdays and weekends.
    Available views: 'year', 'quarter', 'month'
    '''
    time_dict = {'year': data.index.year,
                 'quarter': data.index.quarter,
                 'month': data.index.month}
    plot_range = time_dict[view].unique()
    weekday = (data.index.dayofweek != 5) | (data.index.dayofweek != 6)
    weekend = (data.index.dayofweek == 5) | (data.index.dayofweek == 6)

    if len(plot_range) == 1:
        plt.suptitle('Activity by Date\n', fontsize=22)
        plt.title(f'{view.capitalize()}', fontsize=16)
        plt.xlabel('Date')
        plt.bar(data[weekday].index.date, data[weekday]
                ['this_data'], label='Weekday')
        plt.bar(data[weekend].index.date, data[weekend]
                ['this_data'], color='r', label='Weekend')
        plt.legend(loc=2)
        plt.tight_layout()
        plt.subplots_adjust(top=0.84)
        if savefig:
            plt.savefig('../images/activity_by_date.png', dpi=72)
        plt.show()
    else:
        for i in range(1, time_dict[view].max()+1):
            plt.figure()
            plt.suptitle('Activity by Date\n', fontsize=22)
            plt.title(f'{view.capitalize()}: {i}', fontsize=16)
            plt.xlabel('Date')
            plt.bar(data[(weekday) & (time_dict[view] == i)].index.date, data[(
                weekday) & (time_dict[view] == i)]['this_data'], label='Weekday')
            plt.bar(data[(weekend) & (time_dict[view] == i)].index.date, data[(weekend) & (
                time_dict[view] == i)]['this_data'], color='r', label='Weekend')
            plt.legend(loc=2)
            plt.tight_layout()
            plt.subplots_adjust(top=.84)
            if savefig:
                plt.savefig(
                    f'../images/activity_by_date_{i}.png', dpi=72)
            plt.show()


def decomp_plots(data, savefig=False):
    '''
    Display seasonal decomposition plots
    '''
    decomp = seasonal_decompose(data)
    fig = plt.figure()
    fig = decomp.plot()
    fig.set_size_inches(14, 8)
    plt.xlabel('Date')
    plt.tight_layout()
    if savefig:
        plt.savefig('../images/decomp_plots.png', dpi=72)
    plt.show()


def adf_plot(data, lags=None, savefig=False):
    """
    Plot results of Augmented Dickey-Fuller Test
    Plot Autocorrelation and Partial Autocorrelation Plots
    """
    fig = plt.figure(figsize=(14, 8))
    layout = (2, 2)
    adf_ax = plt.subplot2grid(layout, (0, 0), colspan=2)
    acf_ax = plt.subplot2grid(layout, (1, 0))
    pacf_ax = plt.subplot2grid(layout, (1, 1))

    data.plot(ax=adf_ax)
    p_value = adfuller(data)[1]
    fig.suptitle('Time Series Analysis Plots\n', fontsize=22)
    adf_ax.set_title(f'Dickey-Fuller: p={p_value:.5f}', fontsize=16)
    plot_acf(data, acf_ax, lags)
    plot_pacf(data, pacf_ax, lags)
    plt.tight_layout()
    plt.subplots_adjust(top=0.9)
    if savefig:
        plt.savefig('../images/adf_plot.png')
    plt.show()


def sing_exp_plot(data, alpha, savefig=False):
    plt.figure()
    test_begin = '2016-09-01'
    plt.plot(data.loc[:test_begin, 'this_data'], label='Train Actuals')
    plt.plot(data.loc[:test_begin, 'sing_exp'], label='Train Model')
    plt.plot(data.loc[test_begin:, 'this_data'], label='Test Actuals')
    plt.plot(data.loc[test_begin:, 'sing_exp'], label=f'Test Forecast')
    sing_rmse = root_mean_squared_error(
        data.loc[test_begin:, 'this_data'], data.loc[test_begin:, 'sing_exp'])
    plt.suptitle('Single Exponential Smoothing Forecast\n', fontsize=22)
    plt.title(
        f'Test RMSE = {sing_rmse:.3f} | Alpha = {alpha:.3f}', fontsize=16)
    plt.vlines(test_begin, data['this_data'].min(),
               data['this_data'].max(), linestyles='dashed')
    plt.legend()
    plt.tight_layout()
    plt.subplots_adjust(top=0.84)
    if savefig:
        plt.savefig('../images/exponential_smooth.png', dpi=72)
    plt.show()


def opt_arima_plot(data, zoom=False, savefig=False):
    plt.figure()
    test_begin = '2016-09-01'
    plt.plot(data.loc[:test_begin, 'this_data'], label='Train Actuals')
    plt.plot(data.loc[:test_begin, 'opt_arima'], label='Train Model')
    plt.plot(data.loc[test_begin:, 'this_data'], label='Test Actuals')
    plt.plot(data.loc[test_begin:, 'opt_arima'], label=f'Test Forecast')
    arima_rmse = root_mean_squared_error(
        data.loc[test_begin:, 'this_data'], data.loc[test_begin:, 'opt_arima'])
    plt.suptitle('Optimized Arima Forecast\n', fontsize=22)
    plt.title(f'Test RMSE = {arima_rmse:.3f}', fontsize=16)
    plt.vlines(test_begin, data['this_data'].min(),
               data['this_data'].max(), linestyles='dashed')
    if zoom:
        plt.xlim('2016-08-01', '2016-10-31')
    plt.legend()
    plt.tight_layout()
    plt.subplots_adjust(top=0.84)
    if savefig:
        plt.savefig(f'../images/arima_forecast.png', dpi=72)
    plt.show()


if __name__ == '__main__':

    METRIC_DICT = {'MSE': metrics.mean_squared_error, 'RMSE': root_mean_squared_error, 'R2': metrics.r2_score,
               'MAE': metrics.mean_absolute_error, 'MEDAE': metrics.median_absolute_error, 'MAPE': mean_absolute_percentage_error}




# # create dataframe for all metrics
# rmse_df = create_metrics_df(this_pred_0, 'RMSE')
# mse_df = create_metrics_df(this_pred_0, 'MSE')
# r2_df = create_metrics_df(this_pred_0, 'R2')
# mae_df = create_metrics_df(this_pred_0, 'MAE')
# medae_df = create_metrics_df(this_pred_0, 'MEDAE')
# # MSLE_df = create_metrics_df(this_pred_0, 'MSLE')
# mape_df = create_metrics_df(this_pred_0, 'MAPE')
