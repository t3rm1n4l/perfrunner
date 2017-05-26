import time
from collections import OrderedDict
from copy import copy
from multiprocessing import Process
from typing import Callable, Union

import requests
from decorator import decorator
from logger import logger

from cbagent.collectors import (
    IO,
    PS,
    ActiveTasks,
    DurabilityLatency,
    ElasticStats,
    FTSCollector,
    FTSLatencyCollector,
    N1QLStats,
    Net,
    NSServer,
    NSServerOverview,
    ObserveIndexLatency,
    ObserveSecondaryIndexLatency,
    ReservoirQueryLatency,
    SecondaryDebugStats,
    SecondaryDebugStatsBucket,
    SecondaryDebugStatsIndex,
    SecondaryLatencyStats,
    SecondaryStats,
    SecondaryStorageStats,
    SecondaryStorageStatsMM,
    SpringLatency,
    SubdocLatency,
    TypePerf,
    XATTRLatency,
    XdcrLag,
    XdcrStats,
)
from cbagent.metadata_client import MetadataClient
from perfrunner.helpers.misc import target_hash, uhex
from perfrunner.settings import StatsSettings
from perfrunner.tests import PerfTest


@decorator
def timeit(method: Callable, *args, **kwargs) -> float:
    t0 = time.time()
    method(*args, **kwargs)
    return time.time() - t0  # Elapsed time in seconds


@decorator
def with_stats(method: Callable, *args, **kwargs) -> Union[float, None]:
    with CbAgent(test=args[0], phase=method.__name__):
        return method(*args, **kwargs)


def new_cbagent_settings(test: PerfTest):
    if not test.test_config.stats_settings.enabled:
        return None

    if hasattr(test, 'ALL_BUCKETS'):
        buckets = None
    else:
        buckets = test.test_config.buckets[:1]
    if hasattr(test, 'ALL_HOSTNAMES'):
        hostnames = tuple(test.cluster_spec.yield_hostnames())
    else:
        hostnames = None

    settings = type('settings', (object,), {
        'seriesly_host': StatsSettings.SERIESLY,
        'cbmonitor_host_port': StatsSettings.CBMONITOR,
        'interval': test.test_config.stats_settings.interval,
        'lat_interval': test.test_config.stats_settings.lat_interval,
        'secondary_statsfile': test.test_config.stats_settings.secondary_statsfile,
        'buckets': buckets,
        'indexes': test.test_config.gsi_settings.indexes,
        'hostnames': hostnames,
        'monitored_processes': test.test_config.stats_settings.monitored_processes,
        'bucket_password': test.test_config.bucket.password,
    })()

    if test.cluster_spec.ssh_credentials:
        settings.ssh_username, settings.ssh_password = \
            test.cluster_spec.ssh_credentials
    settings.rest_username, settings.rest_password = \
        test.cluster_spec.rest_credentials

    for _, servers in test.cluster_spec.yield_servers_by_role('index'):
        if servers:
            settings.index_node = servers[0].split(':')[0]

    return settings


class CbAgent:

    def __init__(self, test: PerfTest, phase: str):
        self.test = test
        self.settings = new_cbagent_settings(test=test)

        if self.test.test_config.stats_settings.enabled:
            self.init_clusters(phase=phase)
            self.add_collectors(**test.COLLECTORS)
            self.update_metadata()
            self.start()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.test.test_config.stats_settings.enabled:
            self.stop()
            self.reconstruct()
            self.add_snapshot()

    def init_clusters(self, phase: str):
        self.cluster_map = OrderedDict()

        for cluster_name, servers in self.test.cluster_spec.yield_clusters():
            cluster_id = '{}_{}_{}_{}'.format(cluster_name,
                                              self.test.build.replace('.', ''),
                                              phase,
                                              uhex()[:4])
            master = servers[0].split(':')[0]
            self.cluster_map[cluster_id] = master
        self.test.cbmonitor_clusters = list(self.cluster_map.keys())

    def add_collectors(self,
                       elastic_stats=False,
                       durability=False,
                       fts_latency=False,
                       fts_stats=False,
                       iostat=True,
                       latency=False,
                       index_latency=False,
                       n1ql_latency=False,
                       n1ql_stats=False,
                       net=True,
                       query_latency=False,
                       secondary_debugstats=False,
                       secondary_debugstats_bucket=False,
                       secondary_debugstats_index=False,
                       secondary_index_latency=False,
                       secondary_latency=False,
                       secondary_stats=False,
                       secondary_storage_stats=False,
                       secondary_storage_stats_mm=False,
                       subdoc_latency=False,
                       xattr_latency=False,
                       xdcr_lag=False,
                       xdcr_stats=False):
        self.collectors = []
        self.processes = []

        self.add_collector(NSServer)
        self.add_collector(NSServerOverview)
        self.add_collector(ActiveTasks)

        if self.test.remote.os != 'Cygwin':
            self.add_collector(PS)
            if net:
                self.add_collector(Net)
            if iostat:
                self.add_iostat()
        else:
            self.add_collector(TypePerf)

        if latency:
            self.add_latency_collector(SpringLatency)
        if durability:
            self.add_latency_collector(DurabilityLatency)
        if subdoc_latency:
            self.add_latency_collector(SubdocLatency)
        if xattr_latency:
            self.add_latency_collector(XATTRLatency)

        if query_latency or n1ql_latency:
            self.add_collector(ReservoirQueryLatency)
        if n1ql_stats:
            self.add_collector(N1QLStats)

        if index_latency:
            self.add_collector(ObserveIndexLatency)

        if elastic_stats:
            self.add_collector(ElasticStats, self.test)
        if fts_latency:
            self.add_collector(FTSLatencyCollector, self.test)
        if fts_stats:
            self.add_collector(FTSCollector, self.test)

        if secondary_debugstats:
            self.add_collector(SecondaryDebugStats)
        if secondary_debugstats_bucket:
            self.add_collector(SecondaryDebugStatsBucket)
        if secondary_debugstats_index:
            self.add_collector(SecondaryDebugStatsIndex)
        if secondary_index_latency:
            self.add_collector(ObserveSecondaryIndexLatency)
        if secondary_latency:
            self.add_collector(SecondaryLatencyStats)
        if secondary_stats:
            self.add_collector(SecondaryStats)
        if secondary_storage_stats:
            self.add_collector(SecondaryStorageStats)
        if secondary_storage_stats_mm:
            self.add_collector(SecondaryStorageStatsMM)

        if xdcr_lag:
            self.add_xdcr_lag()
        if xdcr_stats:
            self.add_collector(XdcrStats)

    def add_collector(self, cls, *args):
        for cluster_id, master_node in self.cluster_map.items():
            settings = copy(self.settings)
            settings.cluster = cluster_id
            settings.master_node = master_node

            collector = cls(settings, *args)
            self.collectors.append(collector)

    def add_iostat(self):
        data_path, index_path = self.test.cluster_spec.paths
        partitions = {'data': data_path}
        if hasattr(self.test, 'ddocs'):  # all instances of IndexTest have it
            partitions['index'] = index_path

        for cluster_id, master_node in self.cluster_map.items():
            settings = copy(self.settings)
            settings.cluster = cluster_id
            settings.master_node = master_node
            settings.partitions = partitions

            collector = IO(settings)
            self.collectors.append(collector)

    def add_latency_collector(self, cls):
        for cluster_id, master_node in self.cluster_map.items():
            settings = copy(self.settings)
            settings.cluster = cluster_id
            settings.master_node = master_node
            prefix = self.test.target_iterator.prefix or \
                target_hash(settings.master_node.split(':')[0])

            collector = cls(settings,
                            self.test.test_config.access_settings,
                            prefix)
            self.collectors.append(collector)

    def add_xdcr_lag(self):
        reversed_clusters = list(reversed(self.test.cbmonitor_clusters))

        for i, cluster_id in enumerate(self.cluster_map):
            settings = copy(self.settings)
            settings.cluster = cluster_id
            settings.master_node = self.cluster_map[cluster_id]
            dest_cluster = reversed_clusters[i]
            settings.dest_master_node = self.cluster_map[dest_cluster]

            collector = XdcrLag(settings)
            self.collectors.append(collector)

            if self.test.test_config.xdcr_settings.replication_type == 'unidir':
                break

    def update_metadata(self):
        for collector in self.collectors:
            collector.update_metadata()

    def start(self):
        logger.info('Starting stats collectors')
        self.processes = [Process(target=c.collect) for c in self.collectors]
        for p in self.processes:
            p.start()

    def stop(self):
        logger.info('Terminating stats collectors')
        for p in self.processes:
            p.terminate()

    def reconstruct(self):
        logger.info('Reconstructing measurements')
        for collector in self.collectors:
            if hasattr(collector, 'reconstruct'):
                collector.reconstruct()

    def trigger_reports(self, snapshot: str):
        for report_type in ('html', ):
            url = 'http://{}/reports/{}/?snapshot={}'.format(
                self.settings.cbmonitor_host_port, report_type, snapshot)
            logger.info(url)
            requests.get(url=url)

    def add_snapshot(self):
        self.test.cbmonitor_snapshots = []
        for cluster_id in self.test.cbmonitor_clusters:
            self.settings.cluster = cluster_id
            md_client = MetadataClient(self.settings)
            md_client.add_snapshot(cluster_id)
            self.trigger_reports(cluster_id)

            self.test.cbmonitor_snapshots.append(cluster_id)
