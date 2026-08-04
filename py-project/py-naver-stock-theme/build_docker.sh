echo 'Docker stopping....'
docker stop stock-web-flask-app

echo 'Docker removing....'
docker rm stock-web-flask-app

echo 'Docker image removing....'
docker rmi py-stock-web

echo 'Docker build new py-stock-web'
docker build -t py-stock-web . 

docker-compose up -d
