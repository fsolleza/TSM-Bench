import datetime
import time
import sys

dataset = "d1"
# Check if the correct number of arguments is provided
if len(sys.argv) != 2:
    print("Usage: python script.py <dataset>, defaults to d1")
else: 
    dataset = sys.argv[1].split(".csv")[0]

print(f"transofrming {dataset}")

data_src = open(f'./{dataset}.csv')
data_target= open(f'{dataset}-influxdb.csv','a')
head_line=f"# DDL\n CREATE DATABASE {dataset}\n"
head_line2=f"# DML\n# CONTEXT-DATABASE: {dataset}\n"
data_target.write(head_line)
data_target.write(head_line2)
index=1
line = data_src.readline()

start = time.time()
new_line = '\n'

while True:
    line = data_src.readline()
    if not line:
        break
    if (line.strip() != ''):
        columns = line.split(',')
        date_str=columns[0]
        date_str = str(int(datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S").timestamp()) * 1000)
        id_station = columns[1]
        influx_line = "sensor,id_station="+id_station + " "
        influx_line += ",".join([ f"s{i}={(v if (v != '' and v != new_line) else 'null')}" for i,v in enumerate(columns[2:102]) if (v != '' and v != new_line) ]  )
        influx_line =  influx_line[:-1] + " " + date_str + '\n'
        print("line",influx_line)
        data_target.write(influx_line)
        if(index%1000==0):
            pass
            #passprint(index,end="\r")
        index=index+1
data_target.close()
data_src.close()
print()
print(time.time()-start)
