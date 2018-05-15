
# Introduction

Sometimes AWS cognito can't deliver the message to registered user for confirmation. We have a demand to track these messages and notify the bounced/complaint messages via a Hipchat channel. Here is the workflow

AWS cognito ----> AWS SES ---> AWS SNS ---> AWS Lambda ---> AWS Elasticsearch/Kibana and Hipchat

AWS SES has ability to handle such bounces and complaint emails.

# Walkthrough steps

## AWS cognito 

Choose SES Region; for example, US East
From Email, the email address you want to handle bouncing and complaining

## AWS Elasticsearch 

Granting access to AWS ES cluster's endpoint.
Amazon ES adds support for an authorization layer by integrating with IAM.
The IAM polocy allow or deny Actions (HTTP methods) against Resources (the domain endpoint).

An IAM policy can be 

Resource-based policies – This type of policy is attached to an AWS resource, such as an Amazon S3 bucket, as described in Writing IAM Policies: How to Grant Access to an Amazon S3 Bucket.
Identity-based policies – This type of policy is attached to an identity, such as an IAM user, group, or role.

We can apply both type of policies above by using two strategies to authenticate Amazon ES requests

- Omit the Principal from your policy and specify an IP Condition
- based on the originating Principal

However, given that AWS Lambda function is not in VPC and it doesn't have a specific IPaddress so that we has to use the second strategy.
An example is
``` 
{
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::XXXXXXX:role/lambda_verifyEmailBounceComplaints"
      },
      "Action": "es:*",
      "Resource": "arn:aws:es:us-east-1:XXXXXXX:domain/email-tracking/*"
}
```
We can attach the policies that we build in IAM or in the Amazon ES console to specific IAM entities (in other words, the Amazon ES domain, users, groups, and roles):



To grant access to AWS Elasticsearch endpoint, either specify it in the AWS Elasticsearch Modify Access policy or in AWS IAM role attached to AWS Lambda function

### Modify Access policy
```
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "*"
      },
      "Action": "es:*",
      "Resource": "arn:aws:es:us-east-1:XXXXXXX:domain/email-tracking/*",
      "Condition": {
        "IpAddress": {
          "aws:SourceIp": [
            "trusted IP address"
          ]
        }
      }
    },
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::XXXXXXX:role/lambda_verifyEmailBounceComplaints"
      },
      "Action": "es:*",
      "Resource": "arn:aws:es:us-east-1:XXXXXXX:domain/email-tracking/*"
    }
  ]
}
```

### Create an IAM role which is attached to AWS Lambda function
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Sid": "ES",
            "Effect": "Allow",
            "Action": [
                "es:*"
            ],
            "Resource": [
                "arn:aws:es:us-east-1:XXXXXXX:domain/email-tracking",
                "arn:aws:es:us-east-1:XXXXXXX:domain/email-tracking/*"
            ]
        }
    ]
}
```

## Create AWS Lambda Function using Environment Variables:
Use aws lambda cli or AWS Lambda console to create a lambda function.
https://docs.aws.amazon.com/lambda/latest/dg/get-started-create-function.html

Select the Execution Role is the IAM role created above

We should define the following Environment Variables in advance
- **ELASTICSEARCH_URL**
- **ELASTICSEARCH_INDEX**
- **HIPCHAT_V2_TOKEN**
- **HIPCHAT_ROOMID**

which will be used in hipchat.py

```
es_host = os.getenv('ELASTICSEARCH_URL')
es_index = os.getenv('ELASTICSEARCH_INDEX')
hipchat_v2_token = os.getenv('HIPCHAT_V2_TOKEN')
hipchat_room_id = os.getenv('HIPCHAT_ROOMID')
```

We no need to set the following reserved variables because 
They are generated via the IAM execution role specified for this Lambda function
(assume role concept)

AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_SESSION_TOKEN

AWS_REGION is The AWS region where the Lambda function is executed. 

### Note:
the Lambda handle name must be the name of the main file (omit .py) and the lambda_handler function name (eg: hipchat.lambda_handler) 

## Invoking AWS Lambda function using AWS SNS notification

- Create a SNS topic
- Subscribe to topic: choose protocol which is the AWS Lambda function and the Endpoint is the AWS Lambda ARN above.

https://docs.aws.amazon.com/sns/latest/dg/sns-lambda.html


## Configure AWS SES to notify SNS
In AWS SES console, Email Address > Click on the email address configured to deliver message from cognito.

Under Notification section, choose the Amazon SNS topic we created above for both Bounces and Complaints

https://docs.aws.amazon.com/ses/latest/DeveloperGuide/dashboardconfigureSESnotifications.html


## Tools and Code Explanation 

The project uses pipenv which is a official recommended packaging tool to add packages/dependencies and generate very important Pipfile.lock which produces deterministic builds. Some python packages are not available in AWS Lambda for example elasticsearch. We need to pack them along with our code.


pipenv run pip install -r <(pipenv lock -r) --target ./

which will download and install all dependencies with specific versions written in the Pipfile.lock file

I wrote a small bash file to repeat zip and upload the AWS lambda zip ball file to AWS lambda  for every change. However, you can change it to make it works with a CI/CD such as Travis or Jenkins


Besides, the code is self-explanation. The main lambda_handler function  writes to AWS ES and sends notification to hipchat channel. It is using aws-requests-auth lib which supports AWS Signature Version 4 


ref : https://github.com/DavidMuller/aws-requests-auth/blob/master/README.md


#Troubleshooting

If you encounter the following error in the cloudwatch, it is likely that you misconfigured the IAM policy mentioned above
```
TransportError(403, u'
{
    "Message": "User: arn:aws:sts::XXXXXX:assumed-role/lambda_verifyEmailBounceComplaints/ES_test is not authorized to perform: es:ESHttpPost on resource: email-tracking"
}
'): AuthorizationException
Traceback (most recent call last):
File "/var/task/hipchat.py", line 111, in lambda_handler
body=message)
File "/var/task/elasticsearch/client/utils.py", line 76, in _wrapped
return func(*args, params=params, **kwargs)
File "/var/task/elasticsearch/client/__init__.py", line 319, in index
_make_path(index, doc_type, id), params=params, body=body)
File "/var/task/elasticsearch/transport.py", line 314, in perform_request
status, headers_response, data = connection.perform_request(method, url, params, body, headers=headers, ignore=ignore, timeout=timeout)
File "/var/task/elasticsearch/connection/http_requests.py", line 90, in perform_request
self._raise_error(response.status_code, raw_data)
File "/var/task/elasticsearch/connection/base.py", line 125, in _raise_error
raise HTTP_EXCEPTIONS.get(status_code, TransportError)(status_code, error_message, additional_info)
AuthorizationException: TransportError(403, u'
{
    "Message": "User: arn:aws:sts::XXXXXX:assumed-role/lambda_verifyEmailBounceComplaints/ES_test is not authorized to perform: es:ESHttpPost on resource: email-tracking"
}
')
```
ref: 
https://aws.amazon.com/blogs/security/how-to-control-access-to-your-amazon-elasticsearch-service-domain/

```
MAINTAINER Inspectorio DevOps <devops@inspectorio.com>
```