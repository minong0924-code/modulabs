#!/usr/bin/env python
# -*- coding: utf-8 -*-

from src.sheets_client import get_sheet_data
from src.config import COURSES

sheet_info = COURSES['ai_data_intel']['cohorts'][1]
data = get_sheet_data(sheet_info['sheet_id'], sheet_info['sheet_name'])

print('Loaded rows:', len(data))
print()
print('First row keys:')
if data:
    print(list(data[0].keys()))
    print()
    print('First 3 rows:')
    for i, row in enumerate(data[:3]):
        date_val = row.get('일자', 'N/A')
        name_val = row.get('신청자 이름', 'N/A')
        print(f'Row {i}: Date={date_val}, Name={name_val}')
