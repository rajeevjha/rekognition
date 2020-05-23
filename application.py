import requests
from flask import Flask, request, redirect, jsonify
from twilio.twiml.messaging_response import MessagingResponse
import boto3
import io
from PIL import Image
import json
from io import BytesIO
import os
from werkzeug.utils import secure_filename


application = Flask(__name__)


def print_face_details(faceDetail):
    reply_face_detail = list()
    print (" ############### ")
    print ("Face ({Confidence} %)".format(**faceDetail))

    # emotions
    print ("Emotions -")
    for emotion in faceDetail['Emotions']:
        if emotion['Confidence'] > 90 :
            print ("{Type} : {Confidence}%".format(**emotion))
            reply_face_detail.append("{Type} ".format(**emotion))

    print ("Gender ({0}); confidence - ({1} %)".format(faceDetail['Gender']['Value'], faceDetail['Gender']['Confidence']))
    reply_face_detail.append("{0} ".format(faceDetail['Gender']['Value']))
    print ("Age range: ({0} - {1})".format(faceDetail['AgeRange']['Low'], faceDetail['AgeRange']['High']))
    reply_face_detail.append("Age : {0} - {1} ".format(faceDetail['AgeRange']['Low'], faceDetail['AgeRange']['High']))
    print ("Beard ({0}); confidence - ({1} %)".format(faceDetail['Beard']['Value'], faceDetail['Beard']['Confidence']))
    reply_face_detail.append("Beard ({0}) ".format(faceDetail['Beard']['Value']))
    print ("Eyeglasses ({0}); confidence - ({1} %)".format(faceDetail['Eyeglasses']['Value'], faceDetail['Eyeglasses']['Confidence']))
    reply_face_detail.append("Eyeglasses ({0}) ".format(faceDetail['Eyeglasses']['Value']))
    print ("EyesOpen ({0}); confidence - ({1} %)".format(faceDetail['EyesOpen']['Value'], faceDetail['EyesOpen']['Confidence']))
    print ("MouthOpen ({0}); confidence - ({1} %)".format(faceDetail['MouthOpen']['Value'], faceDetail['MouthOpen']['Confidence']))
    print ("Mustache ({0}); confidence - ({1} %)".format(faceDetail['Mustache']['Value'], faceDetail['Mustache']['Confidence']))
    print ("Smile ({0}); confidence - ({1} %)".format(faceDetail['Smile']['Value'], faceDetail['Smile']['Confidence']))
    reply_face_detail.append("Smile ({0}) ".format(faceDetail['Smile']['Value']))
    print ("Sunglasses ({0}); confidence - ({1} %)".format(faceDetail['Sunglasses']['Value'], faceDetail['Sunglasses']['Confidence']))



    print ("BoundingBox: left={0}, top={1}, width={2}, height={3}".format(faceDetail['BoundingBox']['Left'],faceDetail['BoundingBox']['Top'],faceDetail['BoundingBox']['Width'],faceDetail['BoundingBox']['Height']))

    print ("###############")
    return ",".join(reply_face_detail)



def detect_faces(rekognition, image_binary):
    response = rekognition.detect_faces(Image={'Bytes':image_binary},Attributes=['ALL'])
    reply_detect_faces = list()
    print(str(len(response['FaceDetails'])) + ' - faces detected ')
    for faceDetail in response['FaceDetails']:
        reply_detect_faces.append(print_face_details(faceDetail) + '\n')
    return "\n".join(reply_detect_faces)

def search_faces(rekognition, dynamodb, image_binary):
    reply_search_faces = list()
    response = rekognition.search_faces_by_image(
        CollectionId='family_collection',
        Image={'Bytes':image_binary}
        )

    if len(response['FaceMatches']) == 0:
        print('Person is not indexed')
        reply_search_faces.append('Person is not indexed')
    else:
        for match in response['FaceMatches']:
            print (match['Face']['FaceId'],match['Face']['Confidence'])

            face = dynamodb.get_item(
                TableName='family_collection',
                Key={'RekognitionId': {'S': match['Face']['FaceId']}}
                )

            if 'Item' in face:
                print (face['Item']['FullName']['S'])
                reply_search_faces.append("Hello ! "+ face['Item']['FullName']['S'])
            else:
                print ('no match found in person lookup')
                reply_search_faces.append('No lookup found for person')
    print ('Returning - ' + " ".join(reply_search_faces))
    return " ".join(reply_search_faces)

@application.route("/analyze", methods=['POST'])
def analyze():

    resp = MessagingResponse()

    num_media = int(request.values['NumMedia'])
    media = request.values.get('MediaContentType0', '')
    reply = list()
    if num_media > 0:
        if media.startswith('image/'):
            file_url = request.values['MediaUrl0']
            extension = media.split('/')[1]
            #filename = request.values['MessageSid'] +'.'+extension
            filename = file_url.split("/")[-1].split("?")[0]

            #with open(filename, 'wb') as f:
            #    image_url = request.values['MediaUrl0']
            #    f.write(requests.get(image_url).content)

            rekognition = boto3.client('rekognition', region_name='ap-south-1')
            dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

            image_response = requests.get(file_url)
            image = Image.open(BytesIO(image_response.content))

            stream = io.BytesIO()
            image.save(stream,format='JPEG')
            image_binary = stream.getvalue()

            reply.append(search_faces(rekognition, dynamodb, image_binary))
            reply.append('\n')
            reply.append(detect_faces(rekognition, image_binary))
        else:
            reply.append('Sorry, We can analyze only pictures.')
    else:
        reply.append('Sorry, We can analyze only pictures.')
    resp.message(" ".join(reply))
    return str(resp)


ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])
s3 = boto3.resource('s3')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@application.route('/file-upload', methods=['POST'])
def upload_file():
    # check if the post request has the file part
    if 'file' not in request.files:
        resp = jsonify({'message' : 'No file part in the request'})
        resp.status_code = 400
        return resp
    file = request.files['file']
    fullName = request.form['fullName']
    if file.filename == '':
        resp = jsonify({'message' : 'No file selected for uploading'})
        resp.status_code = 400
        return resp
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        object = s3.Object('aws-rek-bucket','index/'+ filename)
        ret = object.put(Body=file, Metadata={'FullName':fullName} )
        resp = jsonify({'message' : 'File successfully uploaded'})
        resp.status_code = 201
        return resp
    else:
        resp = jsonify({'message' : 'Allowed file types are png, jpg, jpeg, gif'})
        resp.status_code = 400
        return resp



if __name__ == "__main__":
    application.run(host='0.0.0.0')
