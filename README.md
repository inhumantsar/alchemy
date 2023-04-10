# Alchemy

Playing around with llama-loader to interact with codebases. Ideally to provide rewrites, refactoring, and maybe even feature work.

## Getting Started

See [introduction.ipynb](./introduction.ipynb)

## Why?

The cost of switching between frameworks or infrastructure or testing tools is high in nearly all projects. LLMs could make that much less expensive, letting devs be more nimble and cutting down on the tech debt accrued over time.

```python
chat("show me how the lambda functions are created")
```

> The Lambda functions are created using AWS Serverless Application Model (SAM) in a YAML file called lambda.template.yaml. They are defined under the > "Resources" section where each function is given a unique name and accompanying properties.
>
> For example, the "Harvester" function is defined as follows:
>
> ```yaml
> Harvester:
>   Type: AWS::Serverless::Function
>   Properties:
>     PackageType: Image
>     MemorySize: 256
>     ImageUri: 390721581096.dkr.ecr.us-east-2.amazonaws.com/tacostats:v1.5.4
>     ImageConfig:
>       Command:
>         - tacostats.harvester.lambda_handler
>     Role: arn:aws:iam::390721581096:role/tacostats
>     Events:
>       Cron:
>         Type: Schedule
>         Properties:
>           Schedule: cron(55/30 * * * ? *)
>           Enabled: True
>   Metadata:
>     Dockerfile: lambda.Dockerfile
>     DockerContext: "."
> ```
>
> Each Lambda function has similar properties like PackageType, MemorySize, ImageUri, and ImageConfig, which define how the function should be deployed in AWS. Events section defines the triggers for the function. For example, the "Harvester" function is triggered by a scheduled event using a cron expression. Similarly, other functions are defined under the "Resources" section of the YAML file with suitable properties and events.

```python
chat("translate the AWS SAM template to a Pulumi program which uses Python")
```

> To translate the provided AWS Serverless Application Model (SAM) template to a Pulumi program in Python, you can follow these steps:
>
> 1. Ensure that you have the Pulumi CLI and the AWS SDK for Python (Boto3) installed. Additionally, you would need the pulumi python sdk and pulumi_aws > python modules, as shown below.
>
>    ```
>    # Installation
>    pip install pulumi pulumi_aws boto3
>    ```
>
> 2. Create a new Pulumi project using the Python language:
>
>    ```
>    pulumi new aws-python
>    ```
>
> 3. Replace the contents of `__main__.py` with the translated code from the AWS SAM Template.
>
>    ```python
>    import pulumi
>    from pulumi_aws import lambda_, serverless
>    import pulumi_aws as aws
>
>    # Globals
>    timeout = 900
>
>    # Harvester
>    harvester_options = {
>        \'memory_size\': 256,
>        \'image_uri\': \'390721581096.dkr.ecr.us-east-2.amazonaws.com/tacostats:v1.5.4\',
>        \'command\': [\'tacostats.harvester.lambda_handler\'],
>        \'role\': \'arn:aws:iam::390721581096:role/tacostats\'
>    }
>
>    harvester = serverless.Function(\'Harvester\',
>        package_type=\'Image\',
>        timeout=timeout,
>        **harvester_options,
>        events=[
>            (
>                \'Cron\', serverless.FunctionScheduleEvent(
>                schedule=\'cron(55/30 * * * ? *)\',
>                enabled=True,
>                )
>            )
>        ]
>    )
>
>    # ...repeat for the other 7 Lambda functions in the SAM template
>
>    ```
>
> 4. Make sure you have the right credentials and permissions to work with AWS resources using Pulumi.
>
> 5. Run `pulumi up` to deploy the translated infrastructure, and confirm the preview.
>
> The provided code snippet details only the translated "Harvester" Lambda function. Follow the same process for the other seven Lambda functions in the SAM > template. Replace the respective property values accordingly, and modify the events accordingly. This should give you a working Pulumi program in Python > which deploys the equivalent infrastructure as the initial AWS SAM template.
