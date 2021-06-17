# AWS IoT Greengrass V2 Component Using GluonCV Pre-Trained Model to Count People 

Using this project, you can create a Greengrass V2 component that will use a pre-trained GluonCV model to count people from a single frame. The predictions will be summarized in terms of count, the bounding boxes, and frame rate stats over MQTT to IoT Core.

This project targets Linux hosts and was developed using Linux and Mac desktop environments.

## Perform inference with a Pretrained model and GluonCV

Consulting the [Gluon model zoo comparison](https://cv.gluon.ai/model_zoo/detection.html), we select [ssd_512_resnet50_v1_voc](https://cv.gluon.ai/model_zoo/detection.html#id1) as being a good combination of effectively accurate, moderate model size, and was trained with the [Pascal VOC](http://host.robots.ox.ac.uk/pascal/VOC/#history) to predict 20 classes of object--including 'person'. 

_NB- This component could be readily modified to include other GluonCV models or to count other/multiple classes._

These steps follow the [MXNet Tutorial](https://cv.gluon.ai/build/examples_detection/demo_ssd.html#sphx-glr-build-examples-detection-demo-ssd-py) for pre-trainted SSD models.

_Prerequisites:_

* A working installation of [AWS IoT Greengrass v2](https://docs.aws.amazon.com/greengrass/index.html)

* an AWS Account, If you don't have one, see [Set up an AWS account](https://docs.aws.amazon.com/greengrass/v2/developerguide/setting-up.html#set-up-aws-account)

* AWS CLI v2 [installed](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) and [configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html) with permissions to
  * PUT objects into S3

## Overview

This component recipe uses the `Install` and `Run` Lifecycle stages to  

* set up a [python virtual environment](https://pypi.org/project/virtualenv/) for the Greengrass user and install the necesary packages 

* activate that virtual environment and then leave the inference 'free-running' to monitor the source file

The python code is wrapped with shell scripts to help manage the activation of this virtual environment and to pass parameters to the inference program.

| Parameter | usage |
| --- | --- |
| ModelName | name of pre-trained model from GluonCV Zoo to use |
| ClassName | name of class to summarize |
| Threshold | confidence threshold to count a prediction |
| SourceFile | full path of file to read/wait for |
| FrameRate | max frame rate of inference |
| Topic | MQTT topic for results |


## Part 1. Prepare the Greengrass Core

The Greengrass user (usually `ggc_user`) needs write access to **BOTH** their user home AND the SourceFile to read (as the inference script will rename this file as part of capturing/locking the file prior to inference.)

```bash
sudo chmod -R o+w /home/ggc_user
sudo chown -R ggc_user:ggc_group /tmp/data # or appropriate parent dir for the SourceFile
```

_Considerations:_ If the SourceFile is to be repeatedly written by some other process and persistence is not desired, placing the file in a directory on a RAM Disk can be helpful for performance and for power savings. The 'writing' process for that SourceFile should also set the owner or be part of the appropriate group.

## Part 2. Create an inference component for Greengrass

It is common practice when building Greengrass components to maintain a 'shadow' of the artifacts and recipes under user home. This guide continues that practice as it makes some of the preparation convenient. Other workflows are possible.


1. set env vars for name and version

```bash 
export component_name=com.example.count_people
export component_version=1.0.0
```

2. stage the install and inference scripts

```bash
mkdir -p ~/GreengrassCore/artifacts/$component_name/$component_version

cp artifacts/count_people/* ~/GreengrassCore/artifacts/$component_name/$component_version/

cd ~/GreengrassCore/artifacts/$component_name/$component_version/
zip -m $component_name.zip *
```

3. upload script artifacts to S3

```bash
export region='us-west-2'
# or other default region
export acct_num=$(aws sts get-caller-identity --query "Account" --output text)
export bucket_name=greengrass-component-artifacts-$acct_num-$region
# it is common for greengrass roles to be limited to bucket names with these words

# create the bucket if needed
aws s3 mb s3://$bucket_name

# and copy the artifacts to S3
aws s3 sync ~/GreengrassCore/ s3://$bucket_name/
```

4. customize the recipe for the component

```bash
mkdir -p ~/GreengrassCore/recipes/
cp recipes/* ~/GreengrassCore/recipes/

# make sure these values match in the recipe, artifact, and file names
echo $bucket_name
echo $component_name
echo $component_version
# paste in above values for placeholders
vim ~/GreengrassCore/recipes/$component_name-$component_version.json
```

And enter the following content for the recipe, replacing <paste_bucket_name_here> with the name of the bucket you created earlier. Also replace <component\-name>, and <component\-version> as needed.  Also inspect the Configuration Parameters for any changes. 

**NB**: If the Topic parameter is changed, the `accessControl` `resource` will also need to be changed to match.

5. create the GG component with 

```bash
aws greengrassv2 create-component-version --inline-recipe fileb://~/GreengrassCore/recipes/$component_name-$component_version.json
```

## Part 3. Monitor output

The output of the inference should be visible on the `demo/topic` topic, which can easily be inspected on the MQTT Test Client on the AWS IoT Core Console. The messages are also echoed to the log file for the component -- typically `/greengrass/v2/logs/com.example.count_people.log`


## Typical update cycle

To fix a failed deployment:

1. Go to Deployments in the console and remove the offending component from the deployment (check both thing and group level). Deploy.  This will remove the component from the target.

2. Delete the component definition in the console

3. Update the artifacts and push to S3

4. Re-Create the component definition (as this will take a hash from the artifacts). (alternatively, it should be possible to create a new version)

5. Add the newly, re-created component to the deployment and deploy.

_It can be very handy to turn off the Rollback feature on failure to see what was captured/expanded_

If you find yourself iterating through the above cycle many times, it may be easier to develop the component locally first and then upload it. See [Create custom AWS IoT Greengrass components](https://docs.aws.amazon.com/greengrass/v2/developerguide/create-components.html) for information about how to work with components locally on the Greengrass core.
