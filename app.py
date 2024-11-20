from flask import Flask, make_response, render_template, request, redirect
from openai import OpenAI
import json
import base64
import io
from PIL import Image

client = OpenAI(api_key='api-key')

tokens = ['César'] # Un mot de passe pour pas que n'importe qui puisse accéder au site (il est possible d'en mettre plusieurs)

app = Flask(__name__)

@app.route('/style.css') # Mettre le css
def css():
    resp = make_response(render_template("style.css"))
    resp.headers['Content-type'] = 'text/css'
    return resp

@app.route('/',methods=['GET','POST'])
def login() :
    if request.method == 'POST' :
        pwd = request.form.get('password')
        print(pwd)

        resp = make_response(redirect('/home'))
        resp.set_cookie('login',pwd)
        return resp
    
    if request.cookies.get('login') in tokens :
        return redirect('/home')
    
    resp = make_response(render_template('login.html'))
    resp.set_cookie('login','')
    return resp

def resize_image(image_data, max_width=515, max_height=515): # Prépare l'image pour chatGPT (pour qu'elle soit moins longue à envoyer)
    # Ouvrir l'image en mémoire
    image = Image.open(io.BytesIO(image_data))
    
    # Redimensionner l'image en gardant le ratio
    image.thumbnail((max_width, max_height))
    
    # Convertir l'image redimensionnée en bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format=image.format)
    return img_byte_arr.getvalue()

def make_questions(cours) :
    messages = [{'role':'system','content':'L\'utilisateur va t\'envoyer son cours sous forme de photo. tu dois lui créer des questions réponses sous la forme d\'un json : par exemple : {"Comment s\'apelait Louis XIV ?":"Le roi soleil"}. Fais bien attention à la syntaxe Tu dois faire au maximum 5 questions'}]
    messages.append({'role':'user','content':cours})
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )
    print(completion.choices[0].message.content)
    resp = completion.choices[0].message.content.split('\n')

    if 'json' in resp[0] :
        try :
            resp.pop(0)
            resp.pop(-1)
        except :
            return 'Une erreur s\'est produite.\nVeuillez réessayer'
    resp = '\n'.join(resp)

    print(resp)

    return resp


@app.route('/home',methods=['GET','POST'])
def home() :

    if request.method == 'POST' :
        resp = make_response(redirect('/quiz'))
        print(request.files)
        cours = request.form.get('cours')
        photo = request.files["photo_cours"]
        photo = photo.read()
        #print(photo)
        #print(base64.b64decode(photo))
        photo = resize_image(photo)
        photo = base64.b64encode(photo).decode('utf-8')
        print('encodé')

        questions = make_questions([{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{photo}","detail":"low"}}])
        print(questions)


        resp.set_cookie('questions',questions)
        resp.set_cookie('number','0')
        resp.set_cookie('erreurs','{}')
        resp.set_cookie('corrects','{}')
        request.form.get('cours')
        resp.set_cookie('total',str(len(json.loads(questions))))
        return resp
    
    if request.cookies.get('login') in tokens :
        return render_template('home.html')
    else :
        resp = make_response(redirect('/'))
        resp.set_cookie('login','')
        return resp
    
def verifier_reponse(question,answer) :
    messages = [{'role':'system','content':"On va te donner des questions ainsi que des réponses. Ton role va être de déterminer si la réponse donnée par l'utilisateur est globalement correcte. Si sa réponse est correcte, tu répondras True, sinon, tu répondras False"}]
    messages.append({'role':'user','content':f"Question : {question[0]}, Réponse théorique : {question[1]}, Réponse de l'utilisateur : {answer}"})
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    resp = completion.choices[0].message.content.lower()
    print(resp)

    if 'true' in resp :
        is_correct = True
    elif 'false' in resp :
        is_correct = False

    return is_correct
    
@app.route('/quiz',methods=['GET','POST'])
def quiz() :
    questions = request.cookies.get('questions')
    print(questions)
    questions = json.loads(questions)
    number = int(request.cookies.get('number'))
    total = int(request.cookies.get('total'))

    if request.method == 'POST' :
        question = list(questions)[number-1]
        answer = questions[question]

        is_correct = verifier_reponse([question,answer],request.form.get('answer'))
        #is_correct = False
        resp = make_response(redirect('/quiz'))

        if not is_correct :
            erreurs = request.cookies.get('erreurs')
            erreurs = json.loads(erreurs)
            erreurs[question] = [answer,request.form.get('answer')]
            resp.set_cookie('erreurs',json.dumps(erreurs))
        else :
            corrects = request.cookies.get('corrects')
            corrects = json.loads(corrects)
            corrects[question] = [answer, request.form.get('answer')]
            resp.set_cookie('corrects',json.dumps(corrects))
        
        return resp


    if total <= number :
        erreurs = json.loads(request.cookies.get('erreurs'))
        corrects = json.loads(request.cookies.get('corrects'))
        return render_template('results.html',total = total,note =total - len(erreurs),erreurs = erreurs,corrects = corrects)
    
    key = list(questions)[number]

    resp = make_response(render_template('question.html',number=number+1,question=key))
    resp.set_cookie('total',str(len(questions)))
    resp.set_cookie('number',str(number+1))

    return resp
    
@app.route('/logout')
def logout() :
    resp = make_response(redirect('/'))
    resp.set_cookie('login','')
    return resp

if __name__ == '__main__' :
    app.run('0.0.0.0',port=80, debug=False)
