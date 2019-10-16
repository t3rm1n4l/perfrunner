[clusters]
hebe =
    172.23.100.121:kv,index,n1ql
    172.23.100.122:kv,index,n1ql
    172.23.100.123:kv,index,n1ql
    172.23.100.124:kv,index,n1ql
    172.23.100.125:kv,index,n1ql
    172.23.100.126:kv,index,n1ql
    172.23.100.127:kv,index,n1ql
    172.23.100.128:kv,index,n1ql

[clients]
hosts =
    172.23.100.129
    172.23.100.130
    172.23.100.131
    172.23.100.132
    172.23.100.133
    172.23.100.134
credentials = root:couchbase

[storage]
data = /data

[credentials]
rest = Administrator:password
ssh = root:couchbase

[parameters]
OS = CentOS 7
CPU = 2 x Gold 6230 (80 vCPU)
Memory = 128GB
Disk =  Samsung DCT883 960GB
