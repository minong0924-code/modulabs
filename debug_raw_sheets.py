#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gspread
from google.oauth2.service_account import Credentials
import toml

# Streamlit secrets 로드
secrets_path = '.streamlit/secrets.toml'
with open(secrets_path, 'r', encoding='utf-8') as f:
    secrets = toml.load(f)

service_account_info = secrets['gcp_service_account']
credentials = Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
)
client = gspread.authorize(credentials)

sheet_id = '12MZ1OnGKzKnH0dBwKYScAtVycJXcBXkVdA55kzqN7Ag'
sheet_name = '2.2 일자별 신청현황'

spreadsheet = client.open_by_key(sheet_id)
worksheet = spreadsheet.worksheet(sheet_name)

all_values = worksheet.get_all_values()

print(f'Total rows in sheet: {len(all_values)}')
print()
print('Rows 3-14:')
for i in range(2, min(14, len(all_values))):
    row = all_values[i]
    col_0 = row[0] if len(row) > 0 else ''
    col_2 = row[2] if len(row) > 2 else ''
    col_3 = row[3] if len(row) > 3 else ''
    print(f'Row {i+1}: {col_0} | {col_2} | {col_3}')
