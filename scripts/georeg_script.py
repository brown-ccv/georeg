#!/usr/bin/env python

import argparse
import os
import sys
import traceback
import fnmatch
import time
import multiprocessing

parser = argparse.ArgumentParser(description="process and geocode business registries")

parser.add_argument(
    "--year", "-y", type=int, required=True, help="""
        The year of the registry.""")
parser.add_argument(
    "--images", "-i", required=True, help="""
        Path of images to process (not a list, use unix file matching).""")
parser.add_argument(
    "--append", action="store_true", help="""
        Append to the output file instead of overwriting it.""")
parser.add_argument(
    "--debug", action="store_true", help="""
        Draw images showing intermediate output during processing.""")
parser.add_argument(
    "--pre-processed", action="store_true", help="""
        Assume images have been preprocessed by scan-tailor.""")
parser.add_argument(
    "--outdir", "-o", required=True, help="""
        Path to the directory to write out results.""")
parser.add_argument(
    "--state", "-s", default="", required=True, help="""
        US state to get city list.""")

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

def worker_thread_f(images, outname, reg_processor, exc_bucket, file_mutex):
    try:
        reg_processor.make_tess_api()

        for n, image in enumerate(images):
            print "processing: %s (%d/%d)" % (image, n + 1, len(images))

            reg_processor.process_image(image)

            # access to file must be syncronized
            file_mutex.acquire()
            reg_processor.record_to_tsv(outname, 'a')
            file_mutex.release()
    except Exception:
        exc_type, exc_value, exc_trace = sys.exc_info()

        # convert into a string for reporting (traceback objects can't be sent across threads)
        exc_trace = ''.join(traceback.format_tb(exc_trace))

        exc_bucket.put((exc_type, exc_value, exc_trace))

    return reg_processor.mean_ocr_confidence()

if __name__ == "__main__":
    reg_processor = RegistryProcessor()
    reg_processor.initialize_state_year(args.state, args.year)

    reg_processor.draw_debug_images = args.debug
    reg_processor.assume_pre_processed = args.pre_processed
    reg_processor.debugdir = args.outdir

    outname = "%s/%d-compiled.tsv" % (args.outdir, args.year)

    # make some variables to be shared with subprocesses
    manager = multiprocessing.Manager()
    exc_bucket = manager.Queue()
    tsv_file_mutex = manager.Lock()

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
        num_threads = multiprocessing.cpu_count()
    except NotImplementedError:
        print >> sys.stderr, "unable to detect number of cores... defaulting to 4 threads"
        num_threads = 4

    # TODO: make this a process pool to avoid GIL
    # intialize some threading variables
    images_per_thread = len(image_list) / num_threads
    pool = multiprocessing.Pool(processes=num_threads)
    results = []

    start_time = time.time()

    # start threads
    for i in xrange(num_threads):
        assigned_images = []

        if i == num_threads - 1:
            assigned_images = image_list[i * images_per_thread:]
        else:
            assigned_images = image_list[i * images_per_thread:(i + 1) * images_per_thread]

        results.append(pool.apply_async(worker_thread_f, (assigned_images, outname, reg_processor, exc_bucket, tsv_file_mutex)))

    pool.close()
    pool.join()

    num_failed_threads = 0

    # print exception information of failed threads
    while not exc_bucket.empty():
        exc_type, exc_value, exc_trace = exc_bucket.get()

        print >> sys.stderr, "Exception in worker thread:", exc_type, exc_value
        print >> sys.stderr, "Trace back:\n", exc_trace

        num_failed_threads += 1

    # get mean ocr confidence
    mean_conf = 0
    num_scores = 0
    for result in results:
        score = result.get()
        if score != -1:  # -1 means there were no words that were OCRed
            mean_conf += score
            num_scores += 1
    mean_conf /= num_scores * 1.0

    write_mode = "a"

    if not os.path.exists(os.path.join(args.outdir, "OCR_confidence.txt")):
        write_mode = "w"

    with open(os.path.join(args.outdir, "OCR_confidence.txt"), write_mode) as conf_file:
        conf_file.write("year: %d finished with average confidence: %f%%\n" % (args.year, mean_conf))

    elapsed_time = time.time() - start_time

    print "Mean OCR confidence: %d%%" % mean_conf
    print "Number of failed threads: %d" % num_failed_threads
    print "Elapsed time: %d hours, %d minutes and %d seconds" % (elapsed_time / 60 ** 2, (elapsed_time % 60 ** 2) / 60, (elapsed_time % 60 ** 2) % 60)

    print "done"
