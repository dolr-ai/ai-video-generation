GOAL:
1. there is .venv present in the root directory of the project, it is already setup with required dependencies
1. there is MuseTalk/service/README.md present which has instructions to run the service (but this is flask server)
1. i need you to create a fastapi server which will be used to run the service.
1. write endpoints for the following:
    1. generate video
        - takes input of path or link of image
        - takes input of path or link of audio
        - currently does not accept video
    2. status of generation
        - takes input of id of the generation
        - returns the status of the generation
    3. get video
        - takes input of id of the generation
        - returns the video link stored on the server (i should be able to download it from the link, you need not store it on some blob storage, just local file and allow me to curl download it)

1. create a new folder called fastapi_server in the root directory of the project
1. create a structured folder structure inside fastapi_server
1. for reference you can refer to the folder structure and code contents of MuseTalk/service
1. do NOT import any code from MuseTalk/service, you need to write everything from scratch
1. once done create a comprehensive README.md inside fastapi_server folder which will have instructions to run the server

REMEMBER:
1. you need to structure the code in a way such that model loading is separated from rest of the code
1. model will be loaded only once on one fastapi server, request handler server will take care of requests and return status of the generation etc
1. handler server will talk to model server on the localhost for generation purpose