# MA_Dataset_Ingress

This repository contains the code to deploy an AWS SAM application to the cloud. 

This is one of 3 repositories that takes care of ingesting and preprocessing images, training a neuronal network and offering an API solution to classify incomming images.

`/ingress` contains the application code as well as its python dependencies.

`template.yaml` contains the AWS SAM template to deploy it to the cloud. 


On the first deploy please execute:
```bash
sam build --cached --parallel && sam deploy -g
```

`-g` will guide you through the creation of a SAM config file to be used in later deployments


To deploy the application later on use this snipped:
```bash
sam build --cached --parallel && sam deploy
```

As this application does  exceed scertain limits of AWS Lambda, it is built as docker container. As such docker must be installed otherwise `sam build` will generate errors.

To find the default AWS SAM readme, have a look at `README_SAM.md`.