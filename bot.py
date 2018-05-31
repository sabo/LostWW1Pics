import tempfile
import csv

import tweepy

from random import normalvariate, choice
from math import radians, sin, ceil, sqrt
from os.path import join
from time import sleep

from PIL import Image, ImageFilter

# This module is hidden from gitignore and contains the API credentials for twitter
from secret_credentials import *

FINGERS_DIR = 'fingers'
CREDITS_FILE = 'consolidated.csv'

def rotate_random(img):
    # Get the rotation angles, in degrees.
    # This should get us something that ranges from between
    # -30 to 30 degrees, but mostly tends to stick around
    # small values near zero.
    angle_deg = round(min(5, max(-5, normalvariate(0, 1.5))) * 6)
    angle_rad = radians(angle_deg)
    # Make a rotated image. Expand here means that we fit the entire rotated
    # original into the new image, rather than clipping off the corners.
    print("Rotating by {} degrees".format(angle_deg))
    img_rotated = img.rotate(angle_deg, expand=True)

    # hell yeah it's high school trig time
    # Get the crop values. Start by taking the original x and y sizes
    orig_x, orig_y = img.size
    rot_x, rot_y = img_rotated.size
    # Calculate the size of the ugly black triangles
    offset_y = ceil(sin(abs(angle_rad)) * orig_x)
    offset_x = ceil(sin(abs(angle_rad)) * orig_y)

    # Crop out the triangles. This uses the weird PIL coordinate system,
    # so I pretty much just played around with it until it looked right.
    img_cropped = img_rotated.crop((offset_x, offset_y, rot_x - offset_x, rot_y -
                                    offset_y))
    return img_cropped

def motionblur_random(img):
    # info on motion blur from 
    # https://www.packtpub.com/mapt/book/application_development/9781785283932/2/ch02lvl1sec21/motion-blur
    # adapted for PIL
    updown = [0,1,0, 0,1,0, 0,1,0]
    leftright = [0,0,0, 1,1,1, 0,0,0]
    diagl = [1,0,0, 0,1,0, 0,0,1]
    diagr = [0,0,1, 0,1,0, 1,0,0]

    k = choice([updown, leftright, diagl, diagr])
    kern = ImageFilter.Kernel((3,3), k)
    # Apply the filter a bunch to make it stand out
    print("applying motion blur")
    blurred = img.filter(kern)
    for _ in range(0,50):
        blurred = blurred.filter(kern)
    return blurred

def fingers(img, override=None):
    fingers = [
        {'file': 'lower-left.png',
         # 'scale' represents relative area: how much of the image should be covered up
         'scale': 0.1,
         # position is a lambda that returns the upper-left corner of where
         # the pasted image should be put over the original.
         # takes the width and height of the under-image, and the width and
         # height of the scaled over-image
         'position': lambda w, h, o_w, o_h: (0, h - o_h)},
        {'file': 'bottom-left-top-right.png',
         'scale': 1.2, # just to make sure it covers
         'position': lambda _1, _2, _3, _4: (0, 0)},
        {'file': 'right-half.png',
         'scale': 0.5,
         'position': lambda w, h, o_w, o_h: (w - o_w, 0)},
        {'file': 'top-middle.png',
         'scale': 0.2,
         'position': lambda _1, _2, _3, _4: (0, 0)},
        {'file': 'upper-left.png',
         'scale': 0.1,
         'position': lambda _1, _2, _3, _4: (0, 0)},
        {'file': 'upper-right.png',
         'scale': 0.1,
         'position': lambda w, h, o_w, o_h: (w - o_w, 0)},
    ]

    # Pick an overlay.
    if override:
        # ugly but w/e
        overlay = [x for x in fingers if x['file'] == override][0]
    else:
        overlay = choice(fingers)
    print("Applying overlay {}".format(overlay['file']))
    # Load the image, convert to RGBA since we need the alpha channel
    overlay_img = Image.open(join(FINGERS_DIR, overlay['file'])).convert('RGBA')

    # Scale the overlay.
    # Get the overlay's area and aspect ratio
    # and the image's area.
    overlay_area = overlay_img.width * overlay_img.height
    image_area = img.width * img.height
    #
    # ok time for more algebra!
    #
    # We have S, which is how much of the underlying image we want the overlay
    # to cover -- S = (scaled overlay area / image area). 
    # We have R, which is the ratio between the unscaled overlay's area and
    # the image's area -- R = (unscaled overlay area / image area)
    #
    # We know the width and height of the unscaled overlay, and we want to keep
    # its aspect ratio A constant (so it doesn't look weird and distorted).
    # This means that (w/h) = A = (w'/h'), where w' and h' are the
    # scaled overlay's width and height.
    #
    # So (R / S) = (unscaled overlay area) / (scaled overlay area) =>
    # (R / S) = (w*h) / (w'*h').
    # And since w/h = A => h*A = w, and likewise h'*A = w'...
    # (R / S) = (h*A)*h / (h'*A)*h' = (h^2 / h'^2)
    # Rearranging a bit, that gets us to
    # h' = h * sqrt(S/R). 
    # And from there we can get the width just by multiplying by A

    R = overlay_area / image_area
    S = overlay['scale']
    A = overlay_img.width / overlay_img.height

    side_factor = sqrt(S / R)
    new_h = overlay_img.height * side_factor
    # Save casting new_h to int until after we find new_w, for accuracy
    new_w = int(new_h * A)
    new_h = int(new_h)

    # Scale the overlay.
    overlay_scaled = overlay_img.resize((new_w, new_h))
    # Get the upper-left corner of where the overlay should go.
    overlay_pos = overlay['position'](img.width, img.height, new_w, new_h)
    # Paste, using the overlay twice (once as image, once as mask)
    img.paste(overlay_scaled, overlay_pos, overlay_scaled)
    return img

def badificate(img):
    # List of desireable badification processes.
    # Doesn't make sense to, say, do fingers then motionblur
    possible = [
        [rotate_random, motionblur_random, fingers],
        [motionblur_random, fingers],
        [rotate_random, fingers],
        [motionblur_random, rotate_random],
        [fingers],
        [motionblur_random]
    ]
    process = choice(possible)
    for transform in process:
        img = transform(img)
    return img

def main():
    # Open CSV with image info.
    with open(CREDITS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        # need to do this since reader is an iterator, not list, and 
        # choice needs a list
        target = choice([r for r in reader])
    original_image = Image.open(target['filename'])
    mutated_image = badificate(original_image)
    # Save to a temp file object so tweepy can upload it
    tmp_image = tempfile.TemporaryFile()
    mutated_image.save(tmp_image, format="jpeg")

    # Post it to twitter.
    # Authenticate in, both the main account and the credits account
    auth = tweepy.OAuthHandler(CONSUMER_API_KEY, CONSUMER_API_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    credit_auth = tweepy.OAuthHandler(CREDIT_CONSUMER_API_KEY, CREDIT_CONSUMER_API_SECRET)
    credit_auth.set_access_token(CREDIT_ACCESS_TOKEN, CREDIT_ACCESS_TOKEN_SECRET)
    credit_api = tweepy.API(credit_auth)

    # Post image status. Twitter needs a filename, so we just go with the id plus ".jpg"
    print("Posting image to twitter...")
    image_status = api.update_with_media(target['photo_id'] + '.jpg', file=tmp_image)
    # Wait a tick for everything to go thru the system
    sleep(5)
    # Post the credits and link to the original as a reply
    print("Posting credits to twitter...")
    credits_status_text = ".@LostWW1Pics\nOriginal photo:\nCredit: {}\nLink: {}".format(target['credit'],
                                                                         target['permalink'])
    credit_api.update_status(credits_status_text, in_reply_to_status_id=image_status.id_str)

    # We're done! Clean up the temp file
    tmp_image.close()

if __name__ == "__main__":
    main()
