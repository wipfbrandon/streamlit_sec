import streamlit as st
import pandas as pd
import requests

cik_dict = {'Daktronics': '0000915779',
            '3M Company': '0000066740',
            'Union Pacific':'0000100885',
            'Buckle Inc':'0000885245',
            'ConAgra Foods Inc':'0000023217',
            'Valmont Industries':'0000102729',
            'Werner Enterprises':'0000793074',
            'SeaWorld':'0001564902',            
    }

@st.cache_data
def sec_api(cik):
    headers = {'User-Agent': "pythonlearnin@gmail.com"}
#COMPANY SUMMARY
    comp_summ_list = []
    url = f'https://data.sec.gov/submissions/CIK{cik}.json'
    response = requests.get(url, headers=headers)
    cik_name = response.json()['name']
    comp_summ_list.append(cik_name)
    sic_desc = response.json()['sicDescription']
    comp_summ_list.append(sic_desc)
    ticker = response.json()['tickers'][0]
    comp_summ_list.append(ticker)
    exchange = response.json()['exchanges'][0]
    comp_summ_list.append(exchange)
    fye = response.json()['fiscalYearEnd']
    comp_summ_list.append(fye)
    state_inc = response.json()['addresses']['business']['stateOrCountry']
    comp_summ_list.append(state_inc)
    city_inc = response.json()['addresses']['business']['city']
    comp_summ_list.append(city_inc)

#COMPANY FACTS
    response = requests.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json', headers=headers)
    # parsed = json.loads(response.text)
    response_json = response.json()
    entries = response_json['facts']['us-gaap']
    df = pd.DataFrame(entries)
    df_units = df.iloc[2:3] #ONLY WANT ROW 3, WHICH CONTAINS VALUES (I.E. "UNITS")

    df_final = pd.DataFrame()
    def scrub_json(data_list, entry_key, col):
        df = pd.json_normalize(data_list[entry_key])
        df['PERIOD'] = df['fy'].astype(str) + df['fp'].astype(str)
        df = df[df['frame'].astype(str).str.contains('CY') == True]
        df = df.sort_values(by=['filed'], ascending=False)
        df = df.drop_duplicates(subset=['accn'], keep='first')
        df['end'] = pd.to_datetime(df['end'])
        df = df.set_index(['PERIOD', 'form']).sort_index(ascending=False)
        df = df[['end', 'val']]
        df = df.rename(columns={'end':'fin_end_date', 'val':f'{col}'})
        return df

    col_list = ('Revenues', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'NetIncomeLoss',
              'AssetsCurrent', 'LiabilitiesCurrent', 'AccountsReceivableNetCurrent', 'LiabilitiesAndStockholdersEquity',
              'StockholdersEquity', 'NetIncomeLoss', 'Assets', 'InventoryNet', 'Liabilities', 'AccountsPayableCurrent',
              'CommonStockValue', 'ComprehensiveIncomeNetOfTax', 'CostOfGoodsAndServicesSold',
              'Depreciation', 'GrossProfit', 'HeldToMaturitySecurities', 'AvailableForSaleSecurities', 'NetCashProvidedByUsedInFinancingActivities',
              'NetCashProvidedByUsedInInvestingActivities', 'NetCashProvidedByUsedInOperatingActivities', 'OperatingIncomeLoss',
              'ProfitLoss')

    df_final = pd.DataFrame()
    y=0
    for x, col in enumerate(df_units.columns):
        test_list = df_units[col].tolist()[0]
        print(x)
        if col in col_list:
            try:
                df_json = scrub_json(test_list, 'USD', col)
            except:
                try:
                    df_json = scrub_json(test_list, 'pure', col)
                except:
                    try:
                        df_json = scrub_json(test_list, 'shares', col)
                    except:
                        try:
                            df_json = scrub_json(test_list, 'USD/shares', col)
                        except:
                            pass
    
            if y == 0:
                df_final = df_json
                y = y+1
            else:
                df_final = df_final.merge(df_json[f'{col}'], how='left', left_index=True, right_index=True)
        else:
            pass

    df_final = df_final.reset_index()

    days_dict = {'FY':365.00, 'Q3':273.75, 'Q2':182.50, 'Q1':91.25}
    def quarterly_financials(df_source, period='FY'):
        days = days_dict[period]
        df = df_source[df_source['PERIOD'].str.contains(f'{period}')]

        try:
            df['REVENUE_CUSTOM'] = df[['Revenues', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax']].max(axis=1)
            df['REVENUE_CUSTOM'] = df[['Revenues', 'SalesRevenueNet']].max(axis=1)
            df['REVENUE_CUSTOM'] = df[['Revenues']]
            df['PROFIT_MARGIN'] = df['NetIncomeLoss'] / df['REVENUE_CUSTOM']
            df['NET_INCOME_PCT_CHG'] = df['NetIncomeLoss'].pct_change(periods=-1)
            df['CURRENT_RATIO'] = df['AssetsCurrent'] / df['LiabilitiesCurrent']
            df['AR_DAYS'] = (df['AccountsReceivableNetCurrent'] / df['REVENUE_CUSTOM']) * days
            df['LIABILITIES_CUSTOM'] = df['LiabilitiesAndStockholdersEquity'] - df['StockholdersEquity']
        except:
            pass
        df = df.set_index(['PERIOD'])
        df = df.dropna(axis=1, how='all')
        return df

    df_ye = quarterly_financials(df_final, 'FY')
    return df_ye, comp_summ_list

#%% STREAMLIT OUTPUT
add_selectbox = st.sidebar.selectbox(
    'Select your Company',
    (list(cik_dict.keys()))
)

cik_selected = cik_dict[add_selectbox]

#%% SELECT SPECIFIC COMPANY
result_set = sec_api(cik_selected)
df_final = result_set[0]
list_details = result_set[1]

st.title('SEC Financials')
st.sidebar.write(f'INDUSTRY: {list_details[1]}')
st.sidebar.write(f'EXCHANGE: {list_details[3]}')
st.sidebar.write(f'TICKER: {list_details[2]}')
st.sidebar.write(f'FYE: {list_details[4][:2]}/{list_details[4][-2:]}')
st.sidebar.write(f'OPERATIONS: {list_details[6]}, {list_details[5]}')

f"""
Financials Metrics for {add_selectbox}:
"""
st.dataframe(df_final)
'''---
AR Days
'''
st.bar_chart(df_final[['AR_DAYS']])
'''---
Net Income'''
st.line_chart(df_final[['REVENUE_CUSTOM', 'NetIncomeLoss']])
