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
            'Cedar Fair':'0000811532',
            'NVIDIA':'0001045810',
    }

@st.cache_data
def sec_api(cik):
    headers = {'User-Agent': 'pythonlearnin@gmail.com'}
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
    url =f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
    r = requests.get(url, headers=headers)
    
    df = pd.json_normalize(r.json()['facts']['us-gaap'])
    
    df_final = pd.DataFrame()
    keep_list = ('Assets', 'Liabilities', 'StockholdersEquity', 'LiabilitiesAndStockholdersEquity',
                 'Revenues', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax')
    
    y=0
    for x, col in enumerate(df.columns):
        col_name = col.split('.')[0]
        col_type = col.split('.')[1]
    
        if col_name in keep_list:
            if col_type == 'units':
                temp_list = df[col].explode('TEMP')
                df_temp = (pd.DataFrame(temp_list.apply(pd.Series)))
    
                df_temp['PERIOD'] = df_temp['fy'].astype(str) + df_temp['fp'].astype(str)
                df_temp = df_temp.rename(columns={'end':'fin_end_date', 'val':f'{col_name}'})
                df_temp_cy = df_temp[df_temp['frame'].astype(str).str.contains('CY') == True]
                df_temp_cy['frame'] = df_temp_cy['frame'].str.replace('I', '')
    
                def fix_frame(frame, fp):
                    if fp == 'FY':
                        new_fp = 'Q4'
                    else:
                        new_fp = str(fp)
                    if len(frame) < 7:
                        new_frame = str(frame) + new_fp
                    else:
                        new_frame = frame
                    return new_frame
    
                df_temp_cy['NEW_FRAME'] = df_temp_cy.apply(lambda row: fix_frame(row['frame'], row['fp']), axis=1)
                df_temp_cy = df_temp_cy.drop_duplicates(subset=['NEW_FRAME'], keep='first')
                df_temp_cy = df_temp_cy.set_index('NEW_FRAME')
    
                if y==0:
                    df_final = df_temp_cy
                    y=y+1
                else:
                    df_temp_cy = df_temp_cy[[f'{col_name}']]
                    df_final = df_final.merge(df_temp_cy, how='left', left_index=True, right_index=True)

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
    df_q3 = quarterly_financials(df_final, 'Q3')
    return df_ye, comp_summ_list, df_q3

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
df_3q = result_set[2]

st.title('SEC Financials')
st.sidebar.write(f'INDUSTRY: {list_details[1]}')
st.sidebar.write(f'EXCHANGE: {list_details[3]}')
st.sidebar.write(f'TICKER: {list_details[2]}')
st.sidebar.write(f'FYE: {list_details[4][:2]}/{list_details[4][-2:]}')
st.sidebar.write(f'OPERATIONS: {list_details[6]}, {list_details[5]}')

f"""
Financials Metrics for {add_selectbox}:
"""         
'''---
YE Details
'''
st.dataframe(df_final)
'''---
Q3 Details
'''
st.dataframe(df_3q)
'''---
Net Income'''
st.line_chart(df_final[['REVENUE_CUSTOM', 'NetIncomeLoss']])
