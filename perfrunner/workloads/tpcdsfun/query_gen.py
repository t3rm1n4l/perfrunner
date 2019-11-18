import json
from typing import Iterator

MIN_DATE = "2000-01-01T00:00:00"
MAX_DATE = "2014-08-29T23:59:59"

STATEMENTS = {
    'CS01': 'SELECT COUNT(*) FROM call_center',
    'CS02': 'SELECT COUNT(*) FROM catalog_page',
    'CS03': 'SELECT COUNT(*) FROM catalog_returns',
    'CS04': 'SELECT COUNT(*) FROM catalog_sales',
    'CS05': 'SELECT COUNT(*) FROM customer',
    'CS06': 'SELECT COUNT(*) FROM customer_address',
    'CS07': 'SELECT COUNT(*) FROM customer_demographics',
    'CS08': 'SELECT COUNT(*) FROM date_dim',
    'CS09': 'SELECT COUNT(*) FROM household_demographics',
    'CS10': 'SELECT COUNT(*) FROM income_band',
    'CS11': 'SELECT COUNT(*) FROM inventory',
    'CS12': 'SELECT COUNT(*) FROM item',
    'CS13': 'SELECT COUNT(*) FROM promotion',
    'CS14': 'SELECT COUNT(*) FROM reason',
    'CS15': 'SELECT COUNT(*) FROM ship_mode',
    'CS16': 'SELECT COUNT(*) FROM store',
    'CS17': 'SELECT COUNT(*) FROM store_returns',
    'CS18': 'SELECT COUNT(*) FROM store_sales',
    'CS19': 'SELECT COUNT(*) FROM time_dim',
    'CS20': 'SELECT COUNT(*) FROM warehouse',
    'CS21': 'SELECT COUNT(*) FROM web_page',
    'CS22': 'SELECT COUNT(*) FROM web_returns',
    'CS23': 'SELECT COUNT(*) FROM web_sales',
    'CS24': 'SELECT COUNT(*) FROM web_site',
    'TP01': 'WITH customer_total_return AS ('
            'SELECT sr.sr_customer_sk AS ctr_customer_sk, '
            'sr.sr_store_sk AS ctr_store_sk, '
            'SUM(sr.sr_return_amt) AS ctr_total_return '
            'FROM store_returns sr, date_dim dd '
            'WHERE sr.sr_returned_date_sk = dd.d_date_sk '
            'AND dd.d_year = 2000 '
            'GROUP BY sr.sr_customer_sk, sr.sr_store_sk) '
            'SELECT c.c_customer_id FROM customer_total_return ctr1,'
            ' store s, customer c '
            'WHERE ctr1.ctr_total_return > (SELECT VALUE AVG(ctr2.ctr_total_return) * 1.2 '
            'FROM customer_total_return ctr2 '
            'WHERE ctr1.ctr_store_sk = ctr2.ctr_store_sk)[0] '
            'AND s.s_store_sk = ctr1.ctr_store_sk '
            'AND s.s_state = "TN" '
            'AND ctr1.ctr_customer_sk = c.c_customer_sk '
            'ORDER BY c.c_customer_id LIMIT 100;',
    'TP02': 'SELECT s.s_store_name, i.i_item_desc, '
            'sc.revenue, i.i_current_price, i.i_wholesale_cost,'
            ' i.i_brand FROM   store s, item i,'
            ' (SELECT ss_store_sk, Avg(revenue) '
            'AS ave FROM   (SELECT ss_store_sk, '
            'ss_item_sk, Sum(ss.ss_sales_price) '
            'AS revenue FROM   store_sales ss, '
            'date_dim dd WHERE  ss.ss_sold_date_sk = dd.d_date_sk '
            'AND dd.d_month_seq BETWEEN 1199 AND 1199 + 11 '
            'GROUP  BY ss.ss_store_sk, ss.ss_item_sk) sa '
            'GROUP  BY ss_store_sk) sb, '
            '(SELECT ss_store_sk, ss_item_sk, '
            'Sum(ss.ss_sales_price) AS revenue '
            'FROM   store_sales ss, date_dim dd '
            'WHERE  ss.ss_sold_date_sk = dd.d_date_sk '
            'AND dd.d_month_seq BETWEEN 1199 AND 1199 + 11 '
            'GROUP  BY ss.ss_store_sk, ss.ss_item_sk) sc '
            'WHERE  sb.ss_store_sk = sc.ss_store_sk '
            'AND sc.revenue <= 0.1 * sb.ave '
            'AND s.s_store_sk = sc.ss_store_sk '
            'AND i.i_item_sk = sc.ss_item_sk '
            'ORDER  BY s.s_store_name, i.i_item_desc LIMIT 100;',
    'TP03': 'SELECT i_item_id, i_item_desc, '
            'i_category, i_class, i_current_price, '
            'SUM(ss.ss_ext_sales_price) AS itemrevenue, '
            'SUM(ss.ss_ext_sales_price) * 100.0000 / '
            'SUM(SUM(ss.ss_ext_sales_price)) '
            'OVER (PARTITION BY i_class) '
            'AS revenueratio FROM store_sales ss, '
            'item i, date_dim dd '
            'WHERE ss.ss_item_sk = i.i_item_sk '
            'AND i.i_category IN [ "Sports", "Books", "Home" ] '
            'AND ss.ss_sold_date_sk = dd.d_date_sk '
            'AND dd.d_date BETWEEN "1999-02-22" '
            'AND "1999-03-24" GROUP BY i.i_item_id, '
            'i.i_item_desc, i.i_category, i.i_class, '
            'i.i_current_price ORDER BY i.i_category, '
            'i.i_class, i.i_item_id, i.i_item_desc, revenueratio;',
}


DESCRIPTIONS = {
    'CS01': 'COUNT(*) FROM call_center',
    'CS02': 'COUNT(*) FROM catalog_page',
    'CS03': 'COUNT(*) FROM catalog_returns',
    'CS04': 'COUNT(*) FROM catalog_sales',
    'CS05': 'COUNT(*) FROM customer',
    'CS06': 'COUNT(*) FROM customer_address',
    'CS07': 'COUNT(*) FROM customer_demographics',
    'CS08': 'COUNT(*) FROM date_dim',
    'CS09': 'COUNT(*) FROM household_demographics',
    'CS10': 'COUNT(*) FROM income_band',
    'CS11': 'COUNT(*) FROM inventory',
    'CS12': 'COUNT(*) FROM item',
    'CS13': 'COUNT(*) FROM promotion',
    'CS14': 'COUNT(*) FROM reason',
    'CS15': 'COUNT(*) FROM ship_mode',
    'CS16': 'COUNT(*) FROM store',
    'CS17': 'COUNT(*) FROM store_returns',
    'CS18': 'COUNT(*) FROM store_sales',
    'CS19': 'COUNT(*) FROM time_dim',
    'CS20': 'COUNT(*) FROM warehouse',
    'CS21': 'COUNT(*) FROM web_page',
    'CS22': 'COUNT(*) FROM web_returns',
    'CS23': 'COUNT(*) FROM web_sales',
    'CS24': 'COUNT(*) FROM web_site',
    'TP01': 'WITH clause aggregation and groupby',
    'TP02': 'Select with groupby and subquery',
    'TP03': 'Windowed aggregate',
}


def new_statement(qid: str) -> str:
    return STATEMENTS[qid]


def new_description(qid: str) -> str:
    template = DESCRIPTIONS[qid]
    return template


class Query:

    def __init__(self, qid: str):
        self.id = qid

    @property
    def statement(self) -> str:
        return new_statement(self.id)

    @property
    def description(self) -> str:
        return new_description(self.id)


def new_queries(query_set: str) -> Iterator[Query]:
    with open(query_set) as fh:
        queries = json.load(fh)

    for query in queries:
        yield Query(query['id'])
