import json
import logging
from os import environ
import boto3
from helper import check_link, save_img, convert_to_jpeg, get_hashes, get_crop_hash, dict_to_db_map
from uuid import uuid4
import cv2
from pathlib import Path
import os
from typing import Tuple


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

client_dynamodb = boto3.client("dynamodb")
client_s3 = boto3.resource("s3")
bucket_s3 = client_s3.Bucket(environ.get("S3_BUCKET_NAME"))

def insert_dynamodb(
    hashes: dict,
    dataset_orgin_json: dict,
    filename:str,
    ):
    try:
        response = client_dynamodb.put_item(
            TableName=environ.get("TABLE_NAME"),
            Item={
                'id': {'S': hashes.get("crop_res_hash")},
                'classification' : {'S': dataset_orgin_json.get('classification')},
                'link': {'S': dataset_orgin_json.get("url")},
                'hashes' : {'M': dict_to_db_map(hashes)},
                'dataset_origin': {'S': dataset_orgin_json.get("origin")},
                'dataset_origin_json': {'M': dict_to_db_map(dataset_orgin_json)},
                'filename': {'S': filename},
                'group': {'S': dataset_orgin_json.get("group")},
                'data_source': {'S': dataset_orgin_json.get("data_source")},
            }
        )
    except Exception as err:
        LOGGER.warning(err)
        return False
    return True

def check_img_exists(hash:str) -> bool:
    response = client_dynamodb.get_item(
        TableName=environ.get("TABLE_NAME"),
        Key={
            "id": {
                "S": hash,
            }
        }
    )
    if "Item" in response:
        return True
    return False

def process_record(record:dict):
    # get link
    data = json.loads(record.get("body"))
    filename_uuid = uuid4()
    filename = f"{filename_uuid.hex}_{data.get('classification')}"
    
    if data.get("data_source") == "s3_bucket":
        if "bucket_name" not in data:
            LOGGER.error("Data Source is S3_Bucket but no bucket_name given. Aborting!")
            return
        link_check = True
        link = data.get("url")
        ending = ".jpeg"
        LOGGER.info(f"Processing S3 data_source with link: {link}.")
        data_source = data.get("data_source")
        bucket_name = data.get("bucket_name")
        
    elif data.get("data_source")  == "body_image":
        link_check = True
        link = data.get("url")
        ending = ".jpeg"
        data_source = "body_image"
        bucket_name = None
    else:
        link_check, link, ending = check_link(data.get("url"))
        data_source = "url"
        bucket_name = None

    if link_check:
        check_img, path = save_img(
            link=link,
            file_ending=ending,
            data_source=data_source,
            bucket_name=bucket_name,
            filename=filename
        )
        if check_img:
            full_path = convert_to_jpeg(Path(path))

            crop_res_hash = get_crop_hash(str(full_path))
            if check_img_exists(crop_res_hash):
                LOGGER.warning  ("Image already exists in DB")
                return

            tmp = cv2.imread(str(full_path))
            resized = cv2.resize(tmp, (300,300), interpolation=cv2.INTER_AREA)

            upload_path = Path(f"/tmp/upload/{data.get('classification')}")
            upload_path.mkdir(parents=True, exist_ok=True)
            imwrite_file = f"{upload_path}/{filename}.jpeg"

            cv2.imwrite(imwrite_file, resized)
            response = bucket_s3.upload_file(
                imwrite_file,
                f"data_resized/{data.get('classification')}/{filename}.jpeg"
            )
            color_hash, p_hash = get_hashes(str(full_path))
            hashes = {
                "crop_res_hash": crop_res_hash,
                "color_hash": color_hash,
                "p_hash": p_hash,
            }
            insert_dynamodb(hashes, data, f"{filename}.jpeg")
            try:
                if path is not None and os.path.isfile(path):
                    os.remove(path)
                if full_path is not None and os.path.isfile(full_path):
                    os.remove(full_path)
            except BaseException as err:
                LOGGER.error(err)
                return
        else:
            LOGGER.warning("Could not save image")
            LOGGER.warning(data)
            return
    else:
        LOGGER.warning(f"Could not process {data.get('url')}")
        LOGGER.warning(data)
        return



def lambda_handler(event, context):
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """
    LOGGER.info(event)

    for record in event["Records"]:
        # try:
        process_record(record)
        # except Exception as err:
        #     LOGGER.error(err)
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "I am A Teapot 2"
        }),
    }
