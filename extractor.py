#!/usr/bin/env python3
import csv, sys, os, shutil, os.path as osp

import requests

from time import sleep
from bs4 import BeautifulSoup


def process_photo(t, outdir):
    photo_id = t.attrs['id']
    print("Processing photo {}".format(photo_id))
    permalink = 'https://theatlantic.com' + t.find('a', 'permalink').attrs['href']
    photo_url = t.find('source', media="(min-width: 1592px)").attrs['data-srcset']
    credit = t.find('div', 'credit').text.strip()

    filename = osp.join(outdir, photo_id+".jpg")

    # Get the file. This particular technique from https://stackoverflow.com/a/39217788
    with requests.get(photo_url, stream=True) as r:
        # only write the file if we get a good status code
        if r.status_code == 200:
            with open(filename, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
            downloaded = True
        else:
            # Set downloaded to false so we can get it later
            downloaded = False

    # Return the results for the caller to save into a CSV
    return (photo_id, filename, permalink, credit, photo_url, downloaded)

def main():
    # just let it except if we don't give it a filename to parse
    filename = sys.argv[1]
    # make a directory to save the pictures to
    dirname, _ = osp.splitext(osp.basename(filename))
    os.mkdir(dirname)

    # Create CSV file to save results in
    # don't use a with statement, so we don't keep creating/destroying file objects with
    # every line
    c = open(dirname + ".csv", 'w')
    results_file = csv.writer(c)
    results_file.writerow(("photo_id", "filename", "permalink", "credit", "photo_url", "downloaded"))
    # make into BeautifulSoup
    with open(filename) as f:
        soup = BeautifulSoup(f, "html.parser")

    # Find all photos: tag with li, class=photo.
    photos = soup.find_all("li", "photo")
    for photo in photos:
        # Get the photo and record the results, along with metadata.
        results = process_photo(photo, dirname)
        results_file.writerow(results)
        # Sleep for 5s to (hopefully) avoid triggering any rate limiting stuff
        sleep(5)

    print("Done for file {}".format(filename))
    c.close()

if __name__ == "__main__":
    main()
