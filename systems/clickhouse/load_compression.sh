#!/usr/bin/env bash

# THE FOLLOWING SCRIPT WILL SETUP AND LOAD DATASETS FROM A GIVEN FOLDER

# Check if a folder path is provided as an argument
if [ $# -ge 1 ]; then
    folder_path="$1"
else
    echo "No folder path provided."
    exit 1
fi

echo "loading datasets from $folder_path"

# Ensure the results folder exists
results_dir="../../results/compression"
mkdir -p "$results_dir"
output_file="$results_dir/time_and_compression.txt"
echo "### ClickHouse" >> $output_file

# Function to stop and start ClickHouse container
restart_clickhouse() {
    # Stop ClickHouse container if it is running
    docker stop clickhouse-container >/dev/null 2>&1
    sleep 5

    # Start ClickHouse container
    docker start clickhouse-container
    sleep 4
}

    docker start clickhouse-container
    sleep 4

# Function to load a CSV file into ClickHouse
load_file() {
    file_path="$1"
    dataset=$(basename "$file_path" .csv)
    
    # Restart ClickHouse container
    # restart_clickhouse

    # Drop existing table if it exists
    docker exec -it clickhouse-container clickhouse-client --query "DROP TABLE IF EXISTS $dataset;" >/dev/null 2>&1
    sleep 3

    # Create the table in ClickHouse
    docker exec -it clickhouse-container clickhouse-client --query "CREATE TABLE IF NOT EXISTS $dataset ( \
        time DateTime64(9), id_station String, s0 Float32 , s1 Float32 , s2 Float32 , s3 Float32 , s4 Float32 , s5 Float32 , s6 Float32 , s7 Float32 , s8 Float32 , s9 Float32 , s10 Float32 , s11 Float32 , s12 Float32 , s13 Float32 , s14 Float32 , s15 Float32 , s16 Float32 , s17 Float32 , s18 Float32 , s19 Float32 , s20 Float32 , s21 Float32 , s22 Float32 , s23 Float32 , s24 Float32 , s25 Float32 , s26 Float32 , s27 Float32 , s28 Float32 , s29 Float32 , s30 Float32 , s31 Float32 , s32 Float32 , s33 Float32 , s34 Float32 , s35 Float32 , s36 Float32 , s37 Float32 , s38 Float32 , s39 Float32 , s40 Float32 , s41 Float32 , s42 Float32 , s43 Float32 , s44 Float32 , s45 Float32 , s46 Float32 , s47 Float32 , s48 Float32 , s49 Float32 , s50 Float32 , s51 Float32 , s52 Float32 , s53 Float32 , s54 Float32 , s55 Float32 , s56 Float32 , s57 Float32 , s58 Float32 , s59 Float32 , s60 Float32 , s61 Float32 , s62 Float32 , s63 Float32 , s64 Float32 , s65 Float32 , s66 Float32 , s67 Float32 , s68 Float32 , s69 Float32 , s70 Float32 , s71 Float32 , s72 Float32 , s73 Float32 , s74 Float32 , s75 Float32 , s76 Float32 , s77 Float32 , s78 Float32 , s79 Float32 , s80 Float32 , s81 Float32 , s82 Float32 , s83 Float32 , s84 Float32 , s85 Float32 , s86 Float32 , s87 Float32 , s88 Float32 , s89 Float32 , s90 Float32 , s91 Float32 , s92 Float32 , s93 Float32 , s94 Float32 , s95 Float32 , s96 Float32 , s97 Float32 , s98 Float32 , s99 Float32 \
        ) ENGINE = MergeTree() PARTITION BY toYYYYMMDD(time) ORDER BY (id_station, time) Primary key (id_station, time);" >/dev/null 2>&1

    # Load the data into the table
    docker exec -i clickhouse-container clickhouse-client --format_csv_delimiter="," -q "INSERT INTO $dataset FORMAT CSV" < "$file_path"

    # Compute size of the table
    size_output=$(docker exec -it clickhouse-container clickhouse-client --query "SELECT table, formatReadableSize(sum(bytes)) as size FROM system.parts WHERE active AND table='$dataset' GROUP BY table;")
    size=$(echo "$size_output" | tail -n 1 | awk '{print $2}')
    # Log time, size, and dataset name
    echo "$dataset, $size MB" >> "$output_file"
    echo "$dataset, $size MB" 


}

# Iterate through all CSV files in the folder and load them
for file in "$folder_path"/*.csv; do
    if [ -f "$file" ]; then
        load_file "$file"
    fi
done

# Display the compression results
echo "Dataset, Compression, Loading Time"
cat "$output_file"

# Stop ClickHouse container
docker stop clickhouse-container >/dev/null 2>&1
