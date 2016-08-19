#!/usr/bin/env python

import argparse
import os
import sys
import traceback
import fnmatch
import time
import multiprocessing
from datetime import datetime

parser = argparse.ArgumentParser(description="process and geocode business registries")

parser.add_argument(
    "--images", "-i", required=True, help="""
        Path of images to process (not a list, use unix file matching).""")
parser.add_argument(
    "--state", "-s", default="", required=True, help="""
        US state to get city list.""")
parser.add_argument(
    "--year", "-y", type=int, required=True, help="""
        The year of the registry.""")
parser.add_argument(
    "--outdir", "-o", required=True, help="""
        Path to the directory to write out results.""")
parser.add_argument(
    "--append", action="store_true", help="""
        Append to the output file instead of overwriting it.""")
parser.add_argument(
    "--debug", action="store_true", help="""
        Draw images showing intermediate output during processing.
        (also turns off multiprocessing)""")
parser.add_argument(
    "--pre-processed", action="store_true", help="""
        Assume images have been preprocessed by scan-tailor.""")
parser.add_argument(
    "--text-dump-mode", action="store_true", help="""
    If this option is specified georeg will only ocr and record
    business contour text *without* processing anything"""
)

args = parser.parse_args()

# import registry processor based on year
if args.state == 'RI':
    if args.year > 1975:
        from georeg.registry_processor_ri import RegistryProcessorNew as RegistryProcessor
    else:
        from georeg.registry_processor_ri import RegistryProcessorOld as RegistryProcessor
elif args.state == 'TX':
    if args.year == 2005 or args.year == 2011 or args.year == 2010:
        from georeg.registry_processor_tx import RegistryProcessor2000s as RegistryProcessor
    elif args.year == 1999:
        from georeg.registry_processor_tx import RegistryProcessor1999 as RegistryProcessor
    elif args.year == 1995:
        from georeg.registry_processor_tx import RegistryProcessor1995 as RegistryProcessor
    elif args.year == 1990:
        from georeg.registry_processor_tx import RegistryProcessor1990 as RegistryProcessor
    elif args.year == 1980 or args.year == 1985:
        from georeg.registry_processor_tx import RegistryProcessor1980s as RegistryProcessor
    elif args.year == 1975:
        from georeg.registry_processor_tx import RegistryProcessor1975 as RegistryProcessor
    elif args.year in [1965, 1970]:
        from georeg.registry_processor_tx import RegistryProcessor1965 as RegistryProcessor
    elif args.year == 1960:
        from georeg.registry_processor_tx import RegistryProcessor1960 as RegistryProcessor
    elif args.year == 1950 or args.year == 1954:
        from georeg.registry_processor_tx import RegistryProcessor1950s as RegistryProcessor
    else:
        raise ValueError("%d is not a supported year for TX" % (args.year))
else:
    raise ValueError("%s is not a supported state" % (args.state))

# needs to be declared here so that it will inherit from the RegistryProcessor we are using
class DummyTextRecorder(RegistryProcessor):
    """used to record all contour text"""

    def __init__(self):
        super(DummyTextRecorder, self).__init__()

        self.registry_txt = ""

    def _process_contour(self, contour_txt, countor_font_attrs):
        self.registry_txt += "\n" + contour_txt

        return None

    def record_to_tsv(self, path, mode='w'):
        with open(path, mode) as file:
            file.write(self.registry_txt)

def subprocess_f(images, outname, reg_processor, exc_bucket, tsv_file_mutex, print_mutex):

    try:
        reg_processor.make_tess_api()
    except Exception:
        with print_mutex:
            print >>sys.stderr, "exception when initializing tesseract api"
        raise

    for n, image in enumerate(images):
        try:
            with print_mutex:
                print "processing: %s (%d/%d)" % (image, n + 1, len(images))

            reg_processor.process_image(image)

            # access to file must be syncronized
            with tsv_file_mutex:
                reg_processor.record_to_tsv(outname, 'a')

        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()

            # convert into a string for reporting (traceback objects can't be sent across threads)
            exc_trace = ''.join(traceback.format_tb(exc_trace))
            exc_bucket.put((exc_type, exc_value, exc_trace))

    # return performance stats
    return (reg_processor.mean_ocr_confidence(), reg_processor.geocoder_success_rate(), reg_processor.businesses_per_image_std())

if __name__ == "__main__":
    if not args.text_dump_mode:
        reg_processor = RegistryProcessor()
    else:
        reg_processor = DummyTextRecorder()
    reg_processor.initialize_state_year(args.state, args.year)

    reg_processor.draw_debug_images = args.debug
    reg_processor.assume_pre_processed = args.pre_processed
    reg_processor.outdir = args.outdir

    # delete old geoquery log file
    reg_processor.remove_geoquery_log()

    if args.text_dump_mode:
        outname = "%s/%d-text-dump.txt" % (args.outdir, args.year)
    else:
        outname = "%s/%d-compiled.tsv" % (args.outdir, args.year)

    # truncate file if we aren't suppose to append
    if not args.append:
        f = open(outname, 'w')
        f.close()

    # construct actual image list from unix file match pattern
    dir, pattern = os.path.split(args.images)
    image_list = []

    for item in os.listdir(dir):
        if fnmatch.fnmatch(item, pattern):
            image_list.append(os.path.join(dir, item))

    # find number of cores
    try:
        num_processes = multiprocessing.cpu_count()
    except NotImplementedError:
        print >> sys.stderr, "unable to detect number of cores... defaulting to 4 threads"
        num_processes = 4

    if args.debug: # if we are looking at debug images we don't want them being written to by 4 processes at once
        num_processes = 1

    # make some variables to be shared with subprocesses
    manager = multiprocessing.Manager()
    exc_bucket = manager.Queue()
    tsv_file_mutex = manager.Lock()
    print_mutex = manager.Lock()

    # intialize some threading variables
    images_per_process = len(image_list) / num_processes
    pool = multiprocessing.Pool(processes=num_processes)
    results = []

    start_time = time.time()

    # start subprocesses
    for i in xrange(num_processes):
        assigned_images = []

        if i == num_processes - 1:
            assigned_images = image_list[i * images_per_process:]
        else:
            assigned_images = image_list[i * images_per_process:(i + 1) * images_per_process]

        results.append(pool.apply_async(subprocess_f, (assigned_images, outname, reg_processor, exc_bucket, tsv_file_mutex, print_mutex)))

    pool.close()
    pool.join()

    # print exception information of failed processes
    while not exc_bucket.empty():
        exc_type, exc_value, exc_trace = exc_bucket.get()

        print >> sys.stderr, "Exception in subprocess:", exc_type, exc_value
        print >> sys.stderr, "Trace back:\n", exc_trace

    # get performance stats from each subprocess
    ocr_conf_scores = []
    geo_success_rates = []
    bus_count_stds = []
    for result in results:
        ocr_conf_score, geo_success_rate, bus_count_std = result.get()

        if ocr_conf_score != -1:
            ocr_conf_scores.append(ocr_conf_score)
        if geo_success_rate != -1:
            geo_success_rates.append(geo_success_rate)
        if bus_count_std != -1:
            bus_count_stds.append(bus_count_std)

    # get mean of each score
    mean_ocr_conf = sum(ocr_conf_scores) / len(ocr_conf_scores) * 1.0 if len(ocr_conf_scores) > 0 else -1
    mean_geo_sucess_rate = sum(geo_success_rates) / len(geo_success_rates) * 1.0 if len(geo_success_rates) > 0 else -1
    mean_bus_count_std = sum(bus_count_stds) / len(bus_count_stds) * 1.0 if len(bus_count_stds) > 0 else -1

    elapsed_time = time.time() - start_time

    right_now = datetime.today()
    time_of_finish_str = "%d/%d %d:%d" % (right_now.month, right_now.day, right_now.hour, right_now.minute)

    # make performance_stats log entry
    log_entry = "=" * 50 + "\nState: %s, Year: %d, Time of finish: %s\n" + "=" * 50 + \
                """
                \nMean OCR confidence: %f%%\n
                Geocoder success rate: %f%%\n
                Businesses per image deviation: %f\n
                Elapsed time: %d hours, %d minutes and %d seconds\n
                """ + "=" * 50 + "\n\n"
    log_entry = log_entry % (args.state, args.year, time_of_finish_str,
                             mean_ocr_conf, mean_geo_sucess_rate, mean_bus_count_std,
                             elapsed_time / 60 ** 2, (elapsed_time % 60 ** 2) / 60, (elapsed_time % 60 ** 2) % 60)

    write_mode = "a"

    if not os.path.exists(os.path.join(args.outdir, "performance_stats.txt")):
        write_mode = "w"

    # record performance stats
    with open(os.path.join(args.outdir, "performance_stats.txt"), write_mode) as conf_file:
        conf_file.write(log_entry)

    print "Mean OCR confidence: %f%%" % mean_ocr_conf
    print "Geocoder success rate: %f%%" % mean_geo_sucess_rate
    print "Businesses per image deviation: %f" % mean_bus_count_std
    print "Elapsed time: %d hours, %d minutes and %d seconds" % (elapsed_time / 60 ** 2, (elapsed_time % 60 ** 2) / 60, (elapsed_time % 60 ** 2) % 60)

    print "done"