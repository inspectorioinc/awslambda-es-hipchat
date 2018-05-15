#!/bin/bash
# File: publish.sh
# Author: Khuong Nguyen <khuong@inspectorio.com>
# Date: 15.05.2018
# Last Modified Date: 15.05.2018
# Last Modified By: Khuong Nguyen <khuong@inspectorio.com>

zipfile=es_lambda.zip
mkdir -p dist
rm dist/$zipfile
#cd es_lambda 
7z a -r ./dist/$zipfile * 
aws --region us-east-1 lambda update-function-code --function-name HipChat-Post --zip-file fileb://dist/$zipfile
