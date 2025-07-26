WebShopDummy.py – Installation (aktuelle Version)

python -m pip install -r requirements.txt

Mit Docker
'''
docker build -t webshop-backend .
docker run -p 5000:5000 webshop-backend
'''