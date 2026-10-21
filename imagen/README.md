# OpenCV Cartoonization

Web app for a college project using **Flask + OpenCV**.

It lets you:
1. upload an image
2. extract an outline (edge map)
3. generate a cartoonized version
4. tune processing dials directly in the website

## Setup

### 1) Go to project folder
```bash
cd /Users/windows7/Documents/imagen
```

### 2) Create and activate virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3) Install dependencies
```bash
pip install -r requirements.txt
```

### 4) Run the app
```bash
python app.py
```

### 5) Open in browser
`http://127.0.0.1:5000`

## Tech stack
- Flask
- OpenCV
- NumPy
- HTML/CSS/JavaScript
