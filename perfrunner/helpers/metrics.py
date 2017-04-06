import numpy as np
from logger import logger
from seriesly import Seriesly

from perfrunner.settings import StatsSettings


class MetricHelper:

    def __init__(self, test):
        self.test = test
        self.seriesly = Seriesly(StatsSettings.SERIESLY)
        self.test_config = test.test_config
        self.title = test.test_config.test_case.title
        self.cluster_spec = test.cluster_spec
        self.build = test.build

    @staticmethod
    def _get_query_params(metric):
        """Convert metric definition to Seriesly query params. E.g.:

            'avg_xdc_ops' -> {'ptr': '/xdc_ops',
                              'group': 1000000000000, 'reducer': 'avg'}

        Where group is constant."""
        return {'ptr': '/{}'.format(metric[4:]),
                'reducer': metric[:3],
                'group': 1000000000000}

    def _get_metric_info(self, title, order_by=''):
        return {
            'title': title,
            'orderBy': order_by,
        }

    def calc_ycsb_queries(self, value, name, title):
        metric = '{}_{}'.format(self.test_config.name, name)
        title = '{} , {}'.format(title, self.title)
        metric_info = self._get_metric_info(title)
        return value, metric, metric_info

    def calc_avg_n1ql_queries(self):
        metric = '{}_avg_query_requests'.format(self.test_config.name)
        title = 'Avg. Query Throughput (queries/sec), {}'.format(self.title)
        metric_info = self._get_metric_info(title)

        queries = self._calc_avg_n1ql_queries()
        return queries, metric, metric_info

    def _calc_avg_n1ql_queries(self):
        test_time = self.test_config.access_settings.time

        for name, servers in self.cluster_spec.yield_servers_by_role('n1ql'):
            query_node = servers[0].split(':')[0]

            vitals = self.test.rest.get_query_stats(query_node)
            total_requests = vitals['requests.count']
            return int(total_requests / test_time)

    def calc_bulk_n1ql_throughput(self, time_elapsed):
        items = self.test_config.load_settings.items / 4
        time_elapsed /= 1000  # ms -> s
        return round(items / time_elapsed)

    def calc_avg_fts_queries(self, order_by, name='FTS'):
        metric = '{}_avg_query_requests'.format(self.test_config.name)
        title = 'Query Throughput (queries/sec), {}, {} node, {}'.\
                format(self.title,
                       self.test_config.cluster.initial_nodes[0],
                       name)
        metric_info = self._get_metric_info(title, order_by=order_by)

        if name == 'FTS':
            total_queries = 0
            for host in self.test.active_fts_hosts:
                allstats = self.test.rest.get_fts_stats(host)
                key = "{}:{}:{}".format(self.test_config.buckets[0],
                                        self.test.fts_index,
                                        "total_queries")
                if key in allstats:
                    total_queries += allstats[key]

        else:
            allstats = self.test.rest.get_elastic_stats(self.test.fts_master_host)
            total_queries = allstats["_all"]["total"]["search"]["query_total"]

        time_taken = self.test_config.access_settings.time
        qps = total_queries / float(time_taken)
        if qps < 100:
            qps = round(qps, 2)
        else:
            qps = round(qps)
        return qps, metric, metric_info

    def calc_latency_ftses_queries(self, percentile, dbname,
                                   metrics, order_by, name='FTS'):
        if percentile == 0:
            metric = '{}_average'.format(self.test_config.name)
            title = 'Average query latency (ms), {}, {} node, {}'.\
                    format(self.title,
                           self.test_config.cluster.initial_nodes[0],
                           name)
        else:
            metric = self.test_config.name
            title = '{}th percentile query latency (ms), {}, {} node, {}'. \
                    format(percentile,
                           self.title,
                           self.test_config.cluster.initial_nodes[0],
                           name)

        metric_info = self._get_metric_info(title, order_by=order_by)
        timings = []
        db = '{}{}'.format(dbname, self.test.cbagent.cluster_ids[0])
        data = self.seriesly[db].get_all()
        timings += [v[metrics] for v in data.values()]
        if percentile == 0:
            fts_latency = np.average(timings)
        else:
            fts_latency = np.percentile(timings, percentile)
        return round(fts_latency), metric, metric_info

    def calc_ftses_index(self, elapsedtime, order_by, name='FTS'):
        metric = self.test_config.name
        title = 'Index build time(sec), {}, {} node, {}'.\
                format(self.title,
                       self.test_config.cluster.initial_nodes[0],
                       name)
        metric_info = self._get_metric_info(title, order_by=order_by)
        return round(elapsedtime, 1), metric, metric_info

    def calc_fts_index_size(self, index_size_raw, order_by, name='FTS'):
        metric = "{}_indexsize".format(self.test_config.name)
        title = 'Index size (MB), {}, {} node, {}'.\
                format(self.title,
                       self.test_config.cluster.initial_nodes[0],
                       name)
        metric_info = self._get_metric_info(title, order_by=order_by)
        index_size_mb = int(index_size_raw / (1024 ** 2))
        return index_size_mb, metric, metric_info

    def calc_fts_rebalance_time(self, reb_time, order_by, name='FTS'):
        metric = "{}_reb".format(self.test_config.name)
        title = 'Rebalance time (min), {}, {}'.format(self.title, name)
        metric_info = self._get_metric_info(title, order_by=order_by)
        return reb_time, metric, metric_info

    def calc_max_ops(self):
        values = []
        for bucket in self.test_config.buckets:
            db = 'ns_server{}{}'.format(self.test.cbagent.cluster_ids[0], bucket)
            data = self.seriesly[db].get_all()
            values += [v['ops'] for v in data.values()]
        return int(np.percentile(values, 90))

    def calc_xdcr_lag(self, percentile=95):
        metric = '{}_{}th_xdc_lag'.format(self.test_config.name, percentile)
        title = '{}th percentile replication lag (ms), {}'.format(
            percentile, self.title)
        metric_info = self._get_metric_info(title)

        timings = []
        for bucket in self.test_config.buckets:
            db = 'xdcr_lag{}{}'.format(self.test.cbagent.cluster_ids[0], bucket)
            data = self.seriesly[db].get_all()
            timings += [v['xdcr_lag'] for v in data.values()]
        lag = round(np.percentile(timings, percentile), 1)

        return lag, metric, metric_info

    def calc_avg_replication_rate(self, time_elapsed):
        initial_items = self.test_config.load_settings.ops or \
            self.test_config.load_settings.items
        num_buckets = self.test_config.cluster.num_buckets
        avg_replication_rate = num_buckets * initial_items / time_elapsed

        return round(avg_replication_rate)

    def calc_max_drain_rate(self, time_elapsed):
        items_per_node = self.test_config.load_settings.items / \
            self.test_config.cluster.initial_nodes[0]
        drain_rate = items_per_node / time_elapsed

        return round(drain_rate)

    def calc_avg_disk_write_queue(self):
        query_params = self._get_query_params('avg_disk_write_queue')

        disk_write_queue = 0
        for bucket in self.test_config.buckets:
            db = 'ns_server{}{}'.format(self.test.cbagent.cluster_ids[0], bucket)
            data = self.seriesly[db].query(query_params)
            disk_write_queue += list(data.values())[0][0]

        return round(disk_write_queue / 10 ** 6, 2)

    def calc_avg_bg_wait_time(self):
        query_params = self._get_query_params('avg_avg_bg_wait_time')

        avg_bg_wait_time = []
        for bucket in self.test_config.buckets:
            db = 'ns_server{}{}'.format(self.test.cbagent.cluster_ids[0], bucket)
            data = self.seriesly[db].query(query_params)
            avg_bg_wait_time.append(list(data.values())[0][0])
        avg_bg_wait_time = np.mean(avg_bg_wait_time) / 10 ** 3  # us -> ms

        return round(avg_bg_wait_time, 2)

    def calc_avg_couch_views_ops(self):
        query_params = self._get_query_params('avg_couch_views_ops')

        couch_views_ops = 0
        for bucket in self.test_config.buckets:
            db = 'ns_server{}{}'.format(self.test.cbagent.cluster_ids[0], bucket)
            data = self.seriesly[db].query(query_params)
            couch_views_ops += list(data.values())[0][0]

        if self.build < '2.5.0':
            couch_views_ops /= self.test_config.cluster.initial_nodes[0]

        return round(couch_views_ops)

    def calc_query_latency(self, percentile):
        metric = self.test_config.name
        title = '{}th percentile query latency (ms), {}'.format(percentile,
                                                                self.title)

        metric_info = self._get_metric_info(title)
        query_latency = self._calc_query_latency(percentile)

        return query_latency, metric, metric_info

    def _calc_query_latency(self, percentile):
        timings = []
        for bucket in self.test_config.buckets:
            db = 'spring_query_latency{}{}'.format(self.test.cbagent.cluster_ids[0],
                                                   bucket)
            data = self.seriesly[db].get_all()
            timings += [value['latency_query'] for value in data.values()]
        query_latency = np.percentile(timings, percentile)
        if query_latency < 100:
            return round(query_latency, 1)
        return int(query_latency)

    def calc_secondary_scan_latency(self, percentile):
        metric = self.test_config.name
        title = '{}th percentile secondary scan latency (ms), {}'.format(percentile,
                                                                         self.title)
        metric_info = self._get_metric_info(title)

        timings = []
        cluster = ""
        for cid in self.test.cbagent.cluster_ids:
            if "apply_scanworkload" in cid:
                cluster = cid
                break
        db = 'secondaryscan_latency{}'.format(cluster)
        data = self.seriesly[db].get_all()
        timings += [value['Nth-latency'] for value in data.values()]
        timings = list(map(int, timings))
        logger.info("Number of samples are {}".format(len(timings)))
        secondary_scan_latency = np.percentile(timings, percentile) / 1000000

        return round(secondary_scan_latency, 2), metric, metric_info

    def calc_kv_latency(self, operation, percentile, dbname='spring_latency'):
        metric = '{}_{}_{}th'.format(self.test_config.name,
                                     operation,
                                     percentile)
        title = '{}th percentile {} {}'.format(percentile,
                                               operation.upper(),
                                               self.title)
        metric_info = self._get_metric_info(title)

        latency = self._calc_kv_latency(operation, percentile, dbname)

        return latency, metric, metric_info

    def _calc_kv_latency(self, operation, percentile, dbname):
        timings = []
        op_key = 'latency_{}'.format(operation)
        for bucket in self.test_config.buckets:
            db = '{}{}{}'.format(dbname, self.test.cbagent.cluster_ids[0], bucket)
            data = self.seriesly[db].get_all()
            timings += [
                v[op_key] for v in data.values() if op_key in v
            ]
        return round(np.percentile(timings, percentile), 2)

    def calc_observe_latency(self, percentile):
        metric = '{}_{}th'.format(self.test_config.name, percentile)
        title = '{}th percentile {}'.format(percentile, self.title)
        metric_info = self._get_metric_info(title)

        timings = []
        for bucket in self.test_config.buckets:
            db = 'observe{}{}'.format(self.test.cbagent.cluster_ids[0], bucket)
            data = self.seriesly[db].get_all()
            timings += [v['latency_observe'] for v in data.values()]
        latency = round(np.percentile(timings, percentile), 2)

        return latency, metric, metric_info

    def calc_cpu_utilization(self):
        metric = '{}_avg_cpu'.format(self.test_config.name)
        title = 'Avg. CPU utilization (%)'
        title = '{}, {}'.format(title, self.title)
        metric_info = self._get_metric_info(title)

        cluster = self.test.cbagent.cluster_ids[0]
        bucket = self.test_config.buckets[0]

        query_params = self._get_query_params('avg_cpu_utilization_rate')
        db = 'ns_server{}{}'.format(cluster, bucket)
        data = self.seriesly[db].query(query_params)
        cpu_utilazion = round(list(data.values())[0][0])

        return cpu_utilazion, metric, metric_info

    def calc_mem_used(self, max_min='max'):
        metric = '{}_{}_mem_used'.format(self.test_config.name, max_min)
        title = '{}. mem_used (MB), {}'.format(max_min.title(),
                                               self.title)
        metric_info = self._get_metric_info(title)

        query_params = self._get_query_params('max_mem_used')

        mem_used = []
        for bucket in self.test_config.buckets:
            db = 'ns_server{}{}'.format(self.test.cbagent.cluster_ids[0], bucket)
            data = self.seriesly[db].query(query_params)

            mem_used.append(
                round(list(data.values())[0][0] / 1024 ** 2)  # -> MB
            )
        mem_used = eval(max_min)(mem_used)

        return mem_used, metric, metric_info

    def calc_max_beam_rss(self):
        metric = 'beam_rss_max_{}'.format(self.test_config.name)
        title = 'Max. beam.smp RSS (MB), {}'.format(self.title)
        metric_info = self._get_metric_info(title)

        query_params = self._get_query_params('max_beam.smp_rss')

        max_rss = 0
        for cluster_name, servers in self.cluster_spec.yield_clusters():
            cluster = list(filter(lambda name: name.startswith(cluster_name),
                                  self.test.cbagent.cluster_ids))[0]
            for server in servers:
                hostname = server.split(':')[0].replace('.', '')
                db = 'atop{}{}'.format(cluster, hostname)  # Legacy
                data = self.seriesly[db].query(query_params)
                rss = round(list(data.values())[0][0] / 1024 ** 2)
                max_rss = max(max_rss, rss)

        return max_rss, metric, metric_info

    def calc_max_memcached_rss(self):
        metric = '{}_memcached_rss'.format(self.test_config.name)
        title = 'Max. memcached RSS (MB),{}'.format(
            self.title.split(',')[-1]
        )
        metric_info = self._get_metric_info(title)

        query_params = self._get_query_params('max_memcached_rss')

        max_rss = 0
        for (cluster_name, servers), initial_nodes in zip(
                self.cluster_spec.yield_clusters(),
                self.test_config.cluster.initial_nodes,
        ):
            cluster = list(filter(lambda name: name.startswith(cluster_name),
                                  self.test.cbagent.cluster_ids))[0]
            for server in servers[:initial_nodes]:
                hostname = server.split(':')[0].replace('.', '')
                db = 'atop{}{}'.format(cluster, hostname)
                data = self.seriesly[db].query(query_params)
                rss = round(list(data.values())[0][0] / 1024 ** 2)
                max_rss = max(max_rss, rss)

        return max_rss, metric, metric_info

    def calc_avg_memcached_rss(self):
        metric = '{}_avg_memcached_rss'.format(self.test_config.name)
        title = 'Avg. memcached RSS (MB),{}'.format(
            self.title.split(',')[-1]
        )
        metric_info = self._get_metric_info(title)

        query_params = self._get_query_params('avg_memcached_rss')

        rss = list()
        for (cluster_name, servers), initial_nodes in zip(
                self.cluster_spec.yield_clusters(),
                self.test_config.cluster.initial_nodes,
        ):
            cluster = list(filter(lambda name: name.startswith(cluster_name),
                                  self.test.cbagent.cluster_ids))[0]
            for server in servers[:initial_nodes]:
                hostname = server.split(':')[0].replace('.', '')
                db = 'atop{}{}'.format(cluster, hostname)
                data = self.seriesly[db].query(query_params)
                rss.append(round(list(data.values())[0][0] / 1024 ** 2))

        avg_rss = sum(rss) // len(rss)
        return avg_rss, metric, metric_info

    def calc_memory_overhead(self, key_size=20):
        item_size = key_size + self.test_config.load_settings.size
        user_data = self.test_config.load_settings.items * item_size
        user_data *= self.test_config.bucket.replica_number + 1
        user_data /= 2 ** 20

        mem_used, _, _ = self.calc_avg_memcached_rss()
        mem_used *= self.test_config.cluster.initial_nodes[0]

        overhead = 100 * (mem_used / user_data - 1)
        return int(overhead)

    def get_indexing_meta(self, value, index_type, storage=None, unit="min"):
        metric = '{}_{}'.format(self.test_config.name, index_type.lower())
        title = '{} index ({}), {}'.format(index_type, unit, self.title)
        metric_info = self._get_metric_info(title)
        if storage is None:
            metric_info['category'] = index_type.lower()
        else:
            metric_info['category'] = '{}_{}'.format(index_type.lower(), storage)

        return value, metric, metric_info

    def get_memory_meta(self, value, memory_type):
        metric = '{}_{}'.format(self.test_config.name, memory_type.replace(" ", "").lower())
        title = '{} (GB), {}'.format(memory_type, self.title)
        metric_info = self._get_metric_info(title)

        return value, metric, metric_info

    def calc_bnr_throughput(self, time_elapsed, edition, tool):
        metric = '{}_{}_thr_{}'.format(self.test_config.name, tool, edition)
        title = '{} full {} throughput (Avg. MB/sec), {}'.format(
            edition, tool, self.title)
        metric_info = self._get_metric_info(title)

        data_size = self.test_config.load_settings.items * \
            self.test_config.load_settings.size / 2 ** 20  # MB

        avg_throughput = round(data_size / time_elapsed)

        return avg_throughput, metric, metric_info

    def calc_backup_size(self, size, edition):
        metric = '{}_size_{}'.format(self.test_config.name, edition)
        title = '{} backup size (GB), {}'.format(edition, self.title)
        metric_info = self._get_metric_info(title)

        return size, metric, metric_info

    def verify_series_in_limits(self, db, expected_number, metric,
                                larger_is_better=False):
        values = []
        data = self.seriesly[db].get_all()
        values += [value[metric] for value in data.values()]
        values = list(map(float, values))
        logger.info("Number of samples for {} are {}".format(metric, len(values)))
        logger.info("Sample values: {}".format(values))

        if larger_is_better and any(value < expected_number for value in values):
                return False
        else:
            if any(value > expected_number for value in values):
                return False
        return True

    def parse_ycsb_throughput(self):
        with open('YCSB/ycsb_run.log') as fh:
            for line in fh.readlines():
                if line.startswith('[OVERALL], Throughput(ops/sec)'):
                    return int(float(line.split()[-1]))


class DailyMetricHelper(MetricHelper):

    def calc_avg_n1ql_queries(self):
        return 'Avg Query Throughput (queries/sec)', \
            self._calc_avg_n1ql_queries()

    def calc_max_ops(self):
        return 'Max Throughput (ops/sec)', \
            super().calc_max_ops()

    def calc_avg_replication_rate(self, time_elapsed):
        return 'Avg XDCR Rate (items/sec)', \
            super().calc_avg_replication_rate(time_elapsed)

    def calc_ycsb_throughput(self):
        return 'Avg Throughput (ops/sec)', \
            self.parse_ycsb_throughput()

    def calc_backup_throughput(self, time_elapsed):
        data_size = self.test_config.load_settings.items * \
            self.test_config.load_settings.size / 2 ** 20  # MB
        throughput = round(data_size / time_elapsed)

        return 'Avg Throughput (MB/sec)', \
            throughput
