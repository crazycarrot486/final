import os
import base64
import requests
from flask import Flask, request, render_template, jsonify, url_for, send_from_directory
from werkzeug.utils import secure_filename
from flask_cors import CORS
import pandas as pd  # 추천을 위해 pandas 추가
import sys

app = Flask(__name__, static_folder='static')
CORS(app)
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Hugging Face API 정보
API_URL = "https://api-inference.huggingface.co/models/patrickjohncyh/fashion-clip"
headers = {"Authorization": "Bearer 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"}

# 엑셀 파일 불러오기 (추천 시스템 데이터)
clothing_recommendation_df = pd.read_excel(r"C:\Users\hyose\OneDrive\바탕 화면\web programming\clothes.xlsx", sheet_name='Sheet1')
color_recommendation_df = pd.read_excel(r"C:\Users\hyose\OneDrive\바탕 화면\web programming\color.xlsx", sheet_name='Sheet1')

# 파일 확장자 확인 함수
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Hugging Face API에 이미지를 보내서 분석 요청
def query_fashion_clip(image_path, candidate_labels):
    try:
        with open(image_path, "rb") as f:
            img = f.read()

        payload = {
            "parameters": {"candidate_labels": candidate_labels},
            "inputs": base64.b64encode(img).decode("utf-8")
        }
        response = requests.post(API_URL, headers=headers, json=payload)

        if response.status_code != 200:
            return None
        return response.json()
    except Exception as e:
        print(f"API 호출 중 오류 발생: {e}")
        sys.stdout.flush()
        return None

# 분석 결과에서 가장 높은 확률의 레이블을 반환
def get_top_label(output):
    if output and isinstance(output, list):
        top_item = max(output, key=lambda x: x['score'])
        return top_item['label']
    return None

# 의류 종류 추천 함수
def get_top_recommendations(clothing_item, df):
    filtered_df = df[df['antecedents'] == clothing_item]
    sorted_df = filtered_df.sort_values(by='lift', ascending=False)
    top_3 = sorted_df['consequents'].head(3).tolist()
    return top_3

# 색상 추천 함수
def get_top_color_recommendations(clothing_item, df):
    filtered_df = df[df['antecedents'] == clothing_item]
    sorted_df = filtered_df.sort_values(by='lift', ascending=False)
    top_3 = sorted_df['consequents'].head(3).tolist()
    return top_3

# 메인 페이지
@app.route('/')
def index():
    return render_template('index.html')

# 업로드된 파일을 제공하는 라우트
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 분석 요청 처리
@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        if 'file' not in request.files or 'clothing-type' not in request.form:
            return jsonify({'success': False, 'error': '파일 또는 의류 종류가 선택되지 않았습니다.'}), 400

        file = request.files['file']
        clothing_type = request.form['clothing-type']

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # 의류 종류 분석
            if clothing_type == "상의":
                candidate_labels = ["knitwear", "shirt", "polo", "suit jacket", "T-shirt", "jacket", "coat", "hoodie", "sweat shirt"]
            else:
                candidate_labels = ["cotton pants", "sweat pants", "denim pants", "cargo pants", "shorts", "dress pants"]

            output = query_fashion_clip(filepath, candidate_labels)
            if output is None:
                return jsonify({'success': False, 'error': 'API 요청에 실패했습니다.'})

            clothing_label = get_top_label(output)

            # 색상 분석
            color_labels = ["blue clothes", "black clothes", "red clothes", "white clothes", "grey clothes", "beige clothes", "green clothes", "navy clothes"]
            color_output = query_fashion_clip(filepath, color_labels)
            if color_output is None:
                return jsonify({'success': False, 'error': '색상 분석 요청에 실패했습니다.'})

            color_label = get_top_label(color_output)

            # 의류 및 색상 추천 결과 가져오기
            clothing_recommendations = get_top_recommendations(clothing_label, clothing_recommendation_df)
            color_recommendations = get_top_color_recommendations(color_label, color_recommendation_df)

            # 리스트를 문자열로 변환하여 URL에 전달
            clothing_recommendations_str = ",".join(clothing_recommendations)
            color_recommendations_str = ",".join(color_recommendations)

            image_url = f"/uploads/{filename}"
                
            if clothing_type == '상의':
                return jsonify({
                    'success': True,
                    'label': clothing_label,
                    'clothing_type': clothing_type,
                    'color_result': color_label,
                    'clothing_recommendations': clothing_recommendations_str,
                    'color_recommendations': color_recommendations_str,
                    'image_url': image_url,
                    'redirect_url': url_for('result_top', label=clothing_label, color=color_label, image_url=image_url, clothing_recommendations=clothing_recommendations_str, color_recommendations=color_recommendations_str, _external=True)
                })
            else:
                return jsonify({
                    'success': True,
                    'label': clothing_label,
                    'clothing_type': clothing_type,
                    'color_result': color_label,
                    'clothing_recommendations': clothing_recommendations_str,
                    'color_recommendations': color_recommendations_str,
                    'image_url': image_url,
                    'redirect_url': url_for('result_bottom', label=clothing_label, color=color_label, image_url=image_url, clothing_recommendations=clothing_recommendations_str, color_recommendations=color_recommendations_str, _external=True)
                })
        else:
            return jsonify({'success': False, 'error': '잘못된 파일 형식입니다.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': '서버 내부 오류입니다.'}), 500


# 상의 결과 페이지
@app.route('/result/top')
def result_top():
    label = request.args.get('label')
    color = request.args.get('color')
    image_url = request.args.get('image_url')
    
    # 전달된 추천 값을 문자열에서 다시 리스트로 변환
    clothing_recommendations = request.args.get('clothing_recommendations').split(',')
    color_recommendations = request.args.get('color_recommendations').split(',')

    return render_template('top_analyze.html',
                           clothing_result=label,
                           color_result=color,
                           image_url=image_url,
                           clothing_recommendations=clothing_recommendations,
                           color_recommendations=color_recommendations)


# 하의 결과 페이지
@app.route('/result/bottom')
def result_bottom():
    label = request.args.get('label')
    color = request.args.get('color')
    image_url = request.args.get('image_url')
    
    # 전달된 추천 값을 문자열에서 다시 리스트로 변환
    clothing_recommendations = request.args.get('clothing_recommendations').split(',')
    color_recommendations = request.args.get('color_recommendations').split(',')

    return render_template('bottom_analyze.html',
                           clothing_result=label,
                           color_result=color,
                           image_url=image_url,
                           clothing_recommendations=clothing_recommendations,
                           color_recommendations=color_recommendations)


if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
