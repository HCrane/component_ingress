import base64
from io import BytesIO
import logging
import requests
from pathlib import Path
from PIL import Image
from typing import Tuple
import imagehash
import boto3
import botocore
import os

LOGGER = logging.getLogger(__name__)

MAX_RETRY = 5
ALLOWED_CONTENT_TYPE = [
    "image/jpeg",
    "image/png"
]

FILE_EXTENSIONS = {
    "image/jpeg": ".jpeg",
    "image/png": ".png"
}

def convert_to_jpeg(source):
    """Convert image to JPEG.

    Args:
        source (pathlib.Path): Path to source image

    Returns:
        pathlib.Path: path to new image
    """
    destination = source.with_suffix(".jpeg")
    image = Image.open(source)  # Open image
    rgb_image = image.convert("RGB")
    rgb_image.save(destination, format="jpeg", icc_profile=image.info.get("icc_profile"), quality=75)  # Convert image to other format
    
    return destination

def check_link(link:str, count:int = 1) -> Tuple[bool, str, str]:
    """Check if link is valid link and follows redirection recursively

    :param link: http/s link
    :type link: str
    :param count: Parameter for recursion, defaults to 1
    :type count: int, optional
    :return: Returns Touple containing real link to file and file extension
    :rtype: Tuple[bool, str, str]
    """
    if count >= MAX_RETRY:
        LOGGER.warning(f"Return false because MAX_RETRIES reached.")
        return (False, "", "")
    
    try:
        response = requests.head(link, timeout=10)
    except requests.exceptions.ConnectionError:
        LOGGER.warning(f"Max retries or else reached with {link}")
        return (False, "", "")
    except requests.exceptions.Timeout:
        LOGGER.warning(f"Timeout reached with {link}")
        return (False, "", "")
    except requests.exceptions.InvalidURL:
        LOGGER.warning(f"Invalid url supplied with {link}")
        return (False, "", "")
    
    if response.status_code == 301:
        return check_link(response.headers.get("Location"), count + 1)

    if response.status_code == 200:
        if response.headers.get("Content-Type") in ALLOWED_CONTENT_TYPE:
            return(True, link, FILE_EXTENSIONS[response.headers.get("Content-Type")])

    return (False, "", "")

def save_img(link:str, file_ending:str, data_source:str = "url", bucket_name:str = None, filename:str = "tmp") -> Tuple[bool, str]:
    """Save image temporarily

    :param link: link to image / name of file without ending on s3 / bas64 encoded string if data_source == body_image
    :type link: str
    :param file_ending: fileending
    :type file_ending: str
    :param data_source: switch if url or s3 bucket as basis, defaults to "url"
    :type data_source: str, optional
    :param bucket_name: name of s3 bucket, defaults to None
    :type bucket_name: str, optional
    :param filename: filname to save under, defaults to "tmp"
    :type filename: str, optional
    :return: returns touple boolean + path to saved file
    :rtype: Tuple[bool, str]
    """
    path = f"/tmp/{filename}{file_ending}"
    
    if data_source == "s3_bucket":
        if bucket_name is not None:
            bucket = boto3.resource(
                "s3", 
                config=botocore.config.Config(
                signature_version=botocore.UNSIGNED)
            ).Bucket(bucket_name)
            try:
                bucket.download_file(f"{str(link)}.jpg", path)
            except Exception as exception:
                LOGGER.error(f"S3 Bucket Exception: {exception}")
                return (False, "")
            return (True, path)
        else: 
            LOGGER.error("Trying to access AWS S3 Bucket without name. Aborting!")
            return (False, "")
    if data_source == "body_image":
        buffer = BytesIO(base64.b64decode(link))
        img = Image.open(buffer)
        img.save(path)
        return(True, path)
    else:
        try:
            response = requests.get(link, timeout=10)
        except requests.exceptions.ConnectionError:
            LOGGER.warning(f"Max retries or else reached with {link}")
            return (False, "")
        except requests.exceptions.Timeout:
            LOGGER.warning(f"Timeout reached with {link}")
            return (False, "")
        except requests.exceptions.InvalidURL:
            LOGGER.warning(f"Invalid url supplied with {link}")
            return (False, "")
        
        if response.status_code == 200:
            with open(path, "wb") as img:
                img.write(response.content)
            return (True, path)
        return (False, "")

def get_hashes(filepath:str) -> Tuple[str, str]:
  """Generate color_hash and p_hash

  :param filepath: path to image
  :type filepath: str
  :return: Return tuple for all hashes
  :rtype: Tuple[str, str, str]
  """
  p_hash = imagehash.phash(Image.open(filepath))
  color_hash = imagehash.colorhash(Image.open(filepath), binbits=3)

  return ( str(color_hash), str(p_hash))

def get_crop_hash(filepath:str) -> str:
  """Get only crop resistant hash

  :param filepath: path to image
  :type filepath: str
  :return: String representation of ImageHash
  :rtype: str
  """
  crop_resistant_hash = imagehash.crop_resistant_hash(
    Image.open(filepath), 
    min_segment_size=500
  )
  return str(crop_resistant_hash)

def dict_to_db_map(dict: dict) -> dict:
  """Converts given dict to M dynamodb type

  :param dict: dict to convert
  :type dict: dict
  :return: dict to insert
  :rtype: dict
  """
  ret_dict = {}
  
  for key in dict:
    ret_dict[key] = {"S": str(dict.get(key))}
  return ret_dict