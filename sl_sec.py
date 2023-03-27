import streamlit as st
import pandas as pd
import requests
from datetime import date

pd.options.mode.chained_assignment = None  # default='warn'
		
cik_dict = {'Daktronics': '0000915779',
            '3M Company': '0000066740',
            'Union Pacific':'0000100885',
            'Buckle Inc':'0000885245',
            'ConAgra Foods Inc':'0000023217',
            'Valmont Industries':'0000102729',
            'Werner Enterprises':'0000793074',
            'SeaWorld':'0001564902',       
            'Cedar Fair':'0000811532',
            'NVIDIA':'0001045810',}

def set_periods(_lookback_years: int) -> pd.DataFrame:
    curr_qtr = date.today().month // 4 + 1
    curr_year = date.today().year
    period_list = []
    for x in range(0, _lookback_years):
        new_year = curr_year - x
        frame_ye = f'CY{new_year}'
        period_list.append(frame_ye)
        for y in range(4, 0, -1):
            if new_year == curr_year:
                if y >= curr_qtr:
                    pass
                else:
                    frame_qe = f'CY{new_year}Q{y}'
                    period_list.append(frame_qe)
            else:
                frame_qe = f'CY{new_year}Q{y}'
                period_list.append(frame_qe)
    df_frames = pd.DataFrame(index=period_list)
    return df_frames


@st.cache_data
def get_comp_summary(_cik: str) -> dict:
    pass
    _headers = {'User-Agent': "pythonlearnin@gmail.com"}
    url = f'https://data.sec.gov/submissions/CIK{_cik}.json'
    r = requests.get(url, headers=_headers)
    comp_summary = {'cik_name':r.json()['name'],
                    'sic_desc':r.json()['sicDescription'],
                    'ticker':r.json()['tickers'][0],
                    'exchange':r.json()['exchanges'][0],
                    'fye':r.json()['fiscalYearEnd'],
                    'state_inc':r.json()['addresses']['business']['stateOrCountry'],
                    'city_inc':r.json()['addresses']['business']['city'],
		   }
    return comp_summary


@st.cache_data
def get_comp_facts(_cik: str) -> pd.DataFrame:
    _headers = {'User-Agent': "pythonlearnin@gmail.com"}
    url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{_cik}.json'
    r = requests.get(url, headers=_headers)
    df_raw = pd.json_normalize(r.json()['facts']['us-gaap'])
    return df_raw


def clean_comp_facts(df_periods, df_raw):
    df_final = df_periods
    df_sec = df_raw

    keep_list = ('Assets', 'Liabilities', 'StockholdersEquity', 'LiabilitiesAndStockholdersEquity',
             'SalesRevenueNet', 'CostOfGoodsAndServicesSold', ' NetIncomeLoss', 'AccountsReceivableNetCurrent',
             'Revenues', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax')

    for x, col in enumerate(df_sec.columns):
        col_name = col.split('.')[0]
        col_type = col.split('.')[1]

        if col_name in keep_list:
            if col_type == 'units':
                temp_list = df_sec[col].explode('TEMP')
                df_temp = (pd.DataFrame(temp_list.apply(pd.Series)))
                df_temp.frame = df_temp.frame.str.replace('I', '')
                df_temp = df_temp.rename(columns={'val':f'{col_name}'})
                df_temp = df_temp.set_index('frame')

                if df_final.shape[1] == 0:
                    df_final = df_final.merge(df_temp, how='left', left_index=True, right_index=True)
                    df_final = df_final[['end','filed','fy','fp','form',f'{col_name}']]
                else:
                    df_temp = df_temp[[f'{col_name}']]
                    df_final = df_final.merge(df_temp, how='left', left_index=True, right_index=True)

    df_final = df_final.sort_index(ascending=False).reset_index().rename(columns={'index': 'FRAME'})
    return df_final


def custom_revenue(rev, sales_rev, rev_from_cont):
    try:
        rev_list = pd.Series([rev, sales_rev, rev_from_cont]).fillna(0).astype(int)
        return rev_list.max()
    except:
        return 0


def enhance_comp_facts(_years : int = 8, _cik : str = '0001045810', _period : str = 'Q4') -> pd.DataFrame:
    df = clean_comp_facts(set_periods(_years), get_comp_facts(_cik))

    df = df[df['FRAME'].str.contains(f'{_period}')]
    df['YEAR'] = [x[2:6] for x in df['FRAME']]
    df['CALC'] = 0 #DUMMY COLUMN FOR CALCS

    if df['Revenues'].notnull().all():
        df['GROSS_REV'] = df['Revenues']
    elif set(['Revenues', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax']).issubset(df.columns):
        df['GROSS_REV'] = df.apply(lambda row: custom_revenue(row['Revenues'],row['SalesRevenueNet'],row['RevenueFromContractWithCustomerExcludingAssessedTax']),axis=1)
    elif set(['Revenues','RevenueFromContractWithCustomerExcludingAssessedTax']).issubset(df.columns):
        df['GROSS_REV'] = df.apply(lambda row: custom_revenue(row['Revenues'],row['CALC'],row['RevenueFromContractWithCustomerExcludingAssessedTax']),axis=1)

    if 'GROSS_REV' in df:
        df['AR_DAYS'] = ((df['AccountsReceivableNetCurrent'] / df['GROSS_REV']) * 91.25).round(2)

    if set(['NetIncomeLoss','GROSS_REV']).issubset(df.columns):
        df['PROFIT_MARGIN'] = df['NetIncomeLoss'] / df['GROSS_REV']

    if 'NetIncomeLoss' in df:
        df['NET_INCOME_PCT_CHG'] = df['NetIncomeLoss'].pct_change(periods=-1)

    if set(['AssetsCurrent','LiabilitiesCurrent']).issubset(df.columns):
        df['CURRENT_RATIO'] = df['AssetsCurrent'] / df['LiabilitiesCurrent']

    if set(['LiabilitiesAndStockholdersEquity','StockholdersEquity']).issubset(df.columns):
        df['LIABILITIES'] = df['LiabilitiesAndStockholdersEquity'] - df['StockholdersEquity']

    df = df.set_index(['FRAME'])
    df = df.dropna(axis=1, how='all') #DROP ROWS WHERE ALL VALUES = NAN
    return df

#%% STREAMLIT OUTPUT
add_selectbox_company = st.sidebar.selectbox(
    'Select your Company',
    (list(cik_dict.keys()))
)

add_selectbox_years = st.sidebar.selectbox(
    'Lookback (Yrs)',
    ([x for x in range(2, 11)])
)

cik_selected = cik_dict[add_selectbox_company]
lookback = add_selectbox_years

#%% SELECT SPECIFIC COMPANY
company_summ = get_comp_summary(cik_selected)

df_q3 = enhance_comp_facts(lookback, cik_selected, 'Q3')
df_q2 = enhance_comp_facts(lookback, cik_selected, 'Q2')
df_q1 = enhance_comp_facts(lookback, cik_selected, 'Q1')

st.title('SEC Financials')

st.sidebar.write(f"INDUSTRY: {company_summ['sic_desc']}")
st.sidebar.write(f"EXCHANGE: {company_summ['exchange']}")
st.sidebar.write(f"TICKER: {company_summ['ticker']}")
st.sidebar.write(f"FYE: {company_summ['fye'][:2]}/{company_summ['fye'][-2:]}")
st.sidebar.write(f"OPERATIONS: {company_summ['city_inc']}, {company_summ['state_inc']}")

f"""
Financials Metrics for {add_selectbox_company}:
"""         
'''---
Q3 Details
'''
st.dataframe(df_q3)
'''---
Q2 Details
'''
st.dataframe(df_q2)
'''
Q1 Details
'''
st.dataframe(df_q1)
