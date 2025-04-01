import time
from threading import Thread
from threading import Event

from utils.dataset_config_reader import get_dataset_infos
from utils.ingestion.ingestion_data_loading import generate_ingestion_queries


class IngestionResult:
    """ class passed to each thread to log the ingestion results and the status of the ingestion"""
    def __init__(self, tn, n_rows_s):
        self.status = "ok"
        self.tn = tn
        self.insertions = []
        self.evaluated = False
        self.error_message = None
        self.n_rows_s = n_rows_s

    def add_times(self, start_time, end_time, n_rows_inserted=None):
        if n_rows_inserted is None:
            n_rows_inserted = self.n_rows_s
        self.insertions.append((n_rows_inserted, start_time, end_time))

    def set_fail(self, e: Exception):
        print(f"thread {self.tn} failed with {e}")
        self.status = "failed"
        self.error_message = str(e)

    def set_evaluated(self):
        self.evaluated = True

    def is_ok(self):
        return self.status == "ok"


class DataIngestor:
    def __init__(self, system: str, system_module, dataset: str, *, n_rows_s, max_runtime, host, n_threads,
                 warmup_time=None, clean_database=True):

        self.diff_threshold = 1 # we try to insert once every second
        self.n_rows_s = n_rows_s
        self.max_runtime = max_runtime  # max runtime in seconds to compute the required ingestion data

        if system == "questdb":
            self.diff_threshold = 1/4
            self.n_rows_s = int(n_rows_s/4)
            self.max_runtime = max_runtime*4

        self.n_threads = n_threads
        self.host = host
        self.threads = None
        self.event = None
        self.system_module = system_module
        self.dataset = dataset
        self.warmup_time = min(100,360*24*3/n_rows_s if warmup_time is None else warmup_time)
        assert self.warmup_time < max_runtime-100 , "warmup time should be smaller than max runtime and leave some space for the queries to finish"
        self.system = system
        self.clean_database = clean_database # if true the database will be cleaned after the ingestion

    def check_ingestion_rate(self):
        if self.threads is None:
            raise Exception("ingestion not started")
        if not all([thread.is_alive() for thread in self.threads]):
            raise Exception("ingestion not finished")
        return all([ingestion_result.is_ok() for ingestion_result in self.ingestion_results])

    def __enter__(self):
        self.event = Event()
        self.threads = []
        self.ingestion_results = [IngestionResult(tn, self.n_rows_s) for tn in range(self.n_threads)]

        print("generating data")
        insertion_query_f = self.system_module.generate_insertion_query


        ## generate the queries to insert the data
        insertion_queries_generators = generate_ingestion_queries(n_threads=self.n_threads,
                                                                  n_rows_s=self.n_rows_s,
                                                                  max_runtime=self.max_runtime,
                                                                  dataset=self.dataset,
                                                                  system=self.system,
                                                                  insertion_query_f=insertion_query_f)



        print("starting insertion")
        for t_n in range(self.n_threads):
            thread = Thread(target=self.input_data, args=(
                insertion_queries_generators[t_n],  self.ingestion_results[t_n], self.dataset))
            thread.setDaemon(True)
            thread.start()
            self.threads.append(thread)

        print("waiting for ingestion warmup")
        time.sleep(self.warmup_time)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.event.set()
        time.sleep(10)

        print("joining threads")
        for thread in self.threads:
            thread.join()

        time_stop = get_dataset_infos(self.dataset)["time_stop"]
        if self.clean_database:
            print(f"cleaning database from {time_stop}")
            self.system_module.delete_data(date=time_stop, host=self.host, dataset=self.dataset)
        if exc_type is not None:
            print(f"Exception caught: {exc_value}, {exc_type} , {exc_value} continuing...")
            print(traceback)
            # Handle or log the exception here if needed
            raise exc_value
            return True  # Suppresses the exception
        #print(*[ingestion_result.insertions for ingestion_result in self.ingestion_results], sep="\n")




    def input_data(self, insertion_queries , ingestion_logger , dataset=None):
        """
        :param insertion_queries: list or generator containing the query to pass to the write/write_query  function
        :param ingestion_logger:  IngestionResult object to log the ingestion results
        :param dataset: dataset name , some systems  need it)
        """
        print("in input data")

        from systems.utils.connection_class import Connection
        ingestion_logger.set_evaluated()

        ## establisch connection
        connection: Connection = self.system_module.get_connection(host=self.host, dataset=self.dataset)

        thread_start_time = time.time()
        try:
            for sql in insertion_queries:
                if isinstance(sql, str):
                    # n_rows = str(sql).count("(") - 1
                    # min_time = sql.split("VALUES")[1].split(",")[0].replace("(","").replace("'","")
                    # print("number of rows to insert", n_rows,min_time )
                    # print(time.time() - thread_start_time)
                    print("Skipping row parsing")
                elif self.system == "influx": #influx  get a list of points to insert
                    n_rows = len(sql)
                    min_time = sql[0].split(" ")[-1]
                    print("number of rows to insert", n_rows, min_time)
                else:
                    print("could not infer number of rows and last time stamp")

                # stop if the event is set (e.g. the ingestion is finished)
                if self.event.is_set():
                    "setting event"
                    print("Exiting because ingestion should be finished?")
                    break

                start = time.time()
                connection.write(sql) # ingestion is done here
                diff = time.time() - start
                print("Write took {}", diff)
                ingestion_logger.add_times(start, diff)
                if diff <= self.diff_threshold:
                    assert diff > 0
                    time.sleep(self.diff_threshold - diff)
                else:
                    print(f"insertion too slow; took {diff}s")
            if not self.event.is_set():
                ingestion_logger.set_fail(Exception("no more data to insert"))
        except Exception as e:
            ingestion_logger.set_fail(e)
            print("ingestion failed")
            raise e
        finally:
            connection.close()

