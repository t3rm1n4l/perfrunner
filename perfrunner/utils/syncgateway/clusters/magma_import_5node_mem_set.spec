[clusters]
hebe =
    172.23.97.24:kv
    172.23.97.25:kv
    172.23.97.26:kv
    172.23.97.27:kv
    172.23.97.28:kv

[clients]
hosts =
    172.23.97.36
credentials = root:couchbase

[storage]
data = /data
index = /data

[credentials]
rest = Administrator:password
ssh = root:couchbase

[parameters]
OS = CentOS 7
CPU = E5-2680 v3 (48 vCPU)
Memory = 64GB
Disk = Samsung Pro 850
