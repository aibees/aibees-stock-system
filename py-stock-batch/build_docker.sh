echo 'Docker stopping....'
docker stop stock-batch-flask-app

echo 'Docker removing....'
docker rm stock-batch-flask-app

echo 'Docker image removing....'
docker rmi py-stock-batch

echo 'Docker build new py-stock-batch'
docker build -t py-stock-batch . 

docker-compose up -d
