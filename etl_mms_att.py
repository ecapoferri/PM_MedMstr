"""
Extracts att data from MMS/dmp db. Currently deprecated in favor of
    using email subscription reports.
"""
import configparser
import logging
import traceback
from datetime import date, datetime, timedelta
from os import chdir
from os import environ as os_environ

import pandas as pd
from dotenv import load_dotenv
from pandas import DataFrame as Df

from db_engines import mms_db, wh_db
from logging_setup import HDLR_STRM
from table_config import ATT_CFGS, TRAILING_DAYS, VNTGE_FMT, VNTGE_VW_SQL
from time import perf_counter
from pathlib import Path

PERF_START = perf_counter()
CALLING_DIR = Path().cwd()
# Must be set in env on host/container.
ROOT_PATH = Path(os_environ['APPS_ROOT'])
APP_PATH = ROOT_PATH / 'PM_MedMaster'
chdir(APP_PATH)


load_dotenv(ROOT_PATH / '.env')

conf = configparser.ConfigParser()
conf.read('.conf')
conf.read(ROOT_PATH / 'app.cfg')
conf.read(ROOT_PATH / 'conn.cfg')

LOGGER = logging.getLogger(conf['DEFAULT']['LOGGER_NAME'])


# CONFIGS
TBLNM: str = ATT_CFGS['TBLNM']
VNTGE_VW_NM: str = ATT_CFGS['vintage_view_nm']
FIELDS: list[str] = ATT_CFGS['field_stmts']

DF_QUERY_FIELDS: str = ',\n'.join(FIELDS)

DF_QUERY: str = """--sql
        SELECT {f}
        FROM att_inbound
        WHERE connected > '{d}'
        ORDER BY connected DESC
        ;
    """.replace('--sql\n', '')

# ==============================
Q_DATE_FMT: str = r'%Y-%M-%d'
NOW: datetime = datetime.NOW()
MIN_DATE: date = NOW.date() - timedelta(days=float(TRAILING_DAYS))
MIN_DATE_STR: str = MIN_DATE.strftime(Q_DATE_FMT)
VNTGE_TS: str = NOW.strftime(VNTGE_FMT)


def main():
    df: Df
    with mms_db.connect() as conn:
        df = (
                pd.read_sql_query(
                    DF_QUERY.format(
                        # plug in min date
                        d=MIN_DATE_STR,
                        # plug in columns
                        f=DF_QUERY_FIELDS
                    ),
                    conn
                )
                .convert_dtypes()
            )

    with wh_db.connect() as conn:
        # update table
        df.to_sql(TBLNM, conn, if_exists='replace', index=False)
        # create view for data vintage
        conn.execute(VNTGE_VW_SQL.format(nm=VNTGE_VW_NM, ts=VNTGE_TS))

        print(f"\x1b[36;1mSuccessfully loaded {TBLNM} to {wh_db.engine}\x1b[0m")


if __name__ == "__main__":
    main()
