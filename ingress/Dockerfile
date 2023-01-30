FROM public.ecr.aws/lambda/python:3.9
# FROM public.ecr.aws/lambda/python:3.9.2022.12.24.12

RUN yum update -y && yum install libglvnd-glx gcc openssl-devel bzip2-devel libffi-devel wget tar gzip zip make -y

COPY app.py helper.py __init__.py requirements.txt ./

# RUN python3.9 -m venv .venv
# RUN source .venv/bin/activate
RUN python3.9 -m pip install -r requirements.txt -t .

# CMD ["/bin/ls", "-lash"]
# Command can be overwritten by providing a different command in the template directly.
CMD ["app.lambda_handler"]

