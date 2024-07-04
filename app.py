from flask import Flask, request, jsonify, send_file, send_from_directory, Response, session, render_template, redirect, url_for
from flask_cors import cross_origin, CORS
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.exceptions import BadRequest
import os
import json
import logging
from werkzeug.utils import secure_filename
from docx import Document
from docx2pdf import convert
from pdf2docx import Converter
import tempfile
from crewai import Agent, Task, Crew
from crewai_tools import FileReadTool, ScrapeWebsiteTool, MDXSearchTool, SerperDevTool, TXTSearchTool, CSVSearchTool, PDFSearchTool, RagTool

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
CORS(app)
app.config['SECRET_KEY'] = '3175010794'  # Change this to a random secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobstronauts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'signin'

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Directory setup
UPLOAD_FOLDER = 'uploads'
TEMP_FOLDER = 'temp'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'docx', 'pdf'}

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Environment variable configuration for APIs
def configure_apis():
    os.environ["OPENAI_API_KEY"] = "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"
    os.environ["OPENAI_MODEL_NAME"] = "gpt-3.5-turbo"
    os.environ["SERPER_API_KEY"] = "d4e81a83028357dc5af70321c25760e1dd07e44f"

configure_apis()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/signup', methods=['POST', 'GET'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')

        if not all([name, email, password]):
            return jsonify({"error": "All fields are required"}), 400

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"error": "Email already registered"}), 400

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(name=name, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        app.logger.error(f"Error in signup: {str(e)}")
        return jsonify({"error": "An error occurred during signup"}), 500

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form.get('email') or request.json.get('email')
        password = request.form.get('password') or request.json.get('password')

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            if request.is_json:
                return jsonify({"message": "Logged in successfully"}), 200
            else:
                return redirect(url_for('dashboard'))
        else:
            if request.is_json:
                return jsonify({"error": "Invalid email or password"}), 401
            else:
                return render_template('signin.html', error="Invalid email or password")
    return render_template('signin.html')

@app.route('/signout')
@login_required
def signout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html')

@app.route('/user_info')
@login_required
def user_info():
    return jsonify({
        "name": current_user.name,
        "email": current_user.email
    })

@app.route('/blog')
def blog():
    return "Blog coming soon!", 200

@app.route('/contact')
def contact():
    return "Contact page coming soon!", 200

@app.route('/convert_to_pdf', methods=['POST'])
@cross_origin()
@login_required
def convert_to_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(input_path)
        
        output_filename = os.path.splitext(filename)[0] + '.pdf'
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        
        try:
            convert(input_path, output_path)
            return send_file(output_path, as_attachment=True)
        except Exception as e:
            app.logger.error(f"Error converting to PDF: {str(e)}")
            return jsonify({"error": "Error converting file"}), 500
    return jsonify({"error": "File type not allowed"}), 400

@app.route('/convert_to_docx', methods=['POST'])
@cross_origin()
@login_required
def convert_to_docx():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(input_path)
        
        output_filename = os.path.splitext(filename)[0] + '.docx'
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        
        try:
            cv = Converter(input_path)
            cv.convert(output_path)
            cv.close()
            return send_file(output_path, as_attachment=True)
        except Exception as e:
            app.logger.error(f"Error converting to DOCX: {str(e)}")
            return jsonify({"error": "Error converting file"}), 500
    return jsonify({"error": "File type not allowed"}), 400

def structure_output(content, output_type):
    if output_type == "jobRequirements":
        try:
            lines = content.split('\n')
            structured_content = {
                "Must-Have": [],
                "Preferred": [],
                "Nice-to-Have": []
            }
            current_category = None
            for line in lines:
                line = line.strip()
                if line in structured_content:
                    current_category = line
                elif current_category and line:
                    structured_content[current_category].append(line)
            return structured_content
        except:
            return {"Raw Content": content}
    elif output_type == "tailoredResume":
        try:
            sections = content.split('\n\n')
            structured_content = {}
            for section in sections:
                lines = section.split('\n')
                if lines:
                    section_title = lines[0].strip()
                    section_content = '\n'.join(lines[1:]).strip()
                    structured_content[section_title] = section_content
            return structured_content
        except:
            return {"Raw Content": content}
    else:
        return {"Raw Content": content}

@app.route('/process_resume', methods=['POST'])
@cross_origin()
@login_required
def process_resume():
    try:
        if not current_user.is_authenticated:
            return jsonify({"error": "User is not authenticated. Please log in again."}), 401

        raw_data = request.get_data(as_text=True)

        def generate(raw_data):
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError as e:
                logging.error(f"JSON Decode Error: {str(e)}")
                yield f'data: {{"status": "Error", "message": "Invalid JSON in request: {str(e)}"}}\n\n'
                return

            resume_content = data.get('resume_content')
            job_description = data.get('job_description')

            if not resume_content or not job_description:
                yield 'data: {"status": "Error", "message": "Missing resume content or job description"}\n\n'
                return

            # Save resume content to a temporary markdown file for processing
            md_resume_file_path = os.path.join("temp", "temp_resume.md")
            os.makedirs("temp", exist_ok=True)
            with open(md_resume_file_path, 'w', encoding='utf-8') as file:
                file.write(resume_content)

            # Define the tools here
            scrape_tool = ScrapeWebsiteTool()
            search_tool = SerperDevTool()
            pdf_search_tool = PDFSearchTool()
            txt_search_tool = TXTSearchTool()
            read_resume = FileReadTool(file_path=md_resume_file_path)
            semantic_search_resume = MDXSearchTool(mdx=md_resume_file_path)
            rag_tool = RagTool()

            # Initiate CrewAI agents and tasks
            researcher = Agent(
                role="Tech Job Researcher",
                goal="Analyze the job posting description, responsibilities and extract critical information to help craft an ATS friendly resume",
                backstory="You are an experienced researcher with a keen eye for detail. Your expertise in analyzing job postings and extracting relevant information is unmatched.",
                verbose=True,
                allow_delegation=False,
                tools=[scrape_tool, search_tool, pdf_search_tool, txt_search_tool, read_resume, semantic_search_resume, rag_tool]
            )

            resume_strategist = Agent(
                role="Resume Strategist for Engineers",
                goal="Tailor the existing resume to perfectly match the job requirements while maintaining the candidate's authentic experience",
                backstory="With a background in engineering and HR, you excel at customizing resumes to highlight key skills and experiences that align with job postings.",
                verbose=True,
                allow_delegation=False,
                tools=[scrape_tool, search_tool, pdf_search_tool, txt_search_tool, read_resume, semantic_search_resume, rag_tool]
            )

            crew = Crew(
                agents=[researcher, resume_strategist],
                tasks=[
                    Task(
                        description=(
                            f"Analyze the following job description to extract key skills, experiences, and qualifications required. "
                            "Identify both technical and soft skills. Note any specific tools, technologies, or methodologies mentioned. "
                            "Pay attention to preferred qualifications in addition to required ones. "
                            "Create a structured list categorizing these requirements into 'Must-Have', 'Preferred', and 'Nice-to-Have'.\n\n"
                            f"Job Description:\n{job_description}"
                        ),
                        expected_output="A structured list of job requirements categorized into Must-Have, Preferred, and Nice-to-Have skills and qualifications.",
                        agent=researcher
                    ),
                    Task(
                        description=(
                            "Using the job requirements from the previous task and the candidate's existing resume, tailor the resume to highlight the most relevant qualifications. "
                            "Focus on these key areas:\n"
                            "1. Revise the professional summary to align with the job requirements.\n"
                            "2. Reorder and rephrase bullet points in the work experience section to emphasize relevant skills and achievements.\n"
                            "3. Adjust the skills section to prominently feature skills mentioned in the job posting.\n"
                            "4. Incorporate industry-specific keywords and phrases throughout the resume.\n"
                            "5. Ensure the resume maintains ATS-friendliness by using standard section headings and avoiding complex formatting.\n"
                            "Important: Do not invent or remove any information from the original resume. Focus on rephrasing and reorganizing existing content."
                        ),
                        expected_output="A tailored resume highlighting the most relevant qualifications, skills, and experiences matching the job posting.",
                        agent=resume_strategist
                    )
                ],
                verbose=2
            )

            try:
                result = crew.kickoff()
                
                # Ensure we have two parts in the result
                parts = result.split("\n\n", 1)
                if len(parts) < 2:
                    raise ValueError("Unexpected result format from CrewAI")
                
                job_analysis_result, tailored_resume_content = parts

                structured_job_analysis = structure_output(job_analysis_result, "jobRequirements")
                structured_tailored_resume = structure_output(tailored_resume_content, "tailoredResume")

                yield f'data: {{"status": "Update", "type": "jobRequirements", "message": "Job requirements analysis completed", "data": {json.dumps(structured_job_analysis)}}}\n\n'
                yield f'data: {{"status": "Update", "type": "tailoredResume", "message": "Resume optimization completed", "data": {json.dumps(structured_tailored_resume)}}}\n\n'
                yield f'data: {{"status": "Complete", "message": "Resume processing completed successfully"}}\n\n'
            except Exception as e:
                logging.error(f"Error executing crew tasks: {str(e)}")
                yield f'data: {{"status": "Error", "message": "Error during resume processing: {str(e)}"}}\n\n'
                yield f'data: {{"status": "Error", "message": "Error during resume processing: {str(e)}"}}\n\n'
                return

        return Response(generate(raw_data), mimetype='text/event-stream')
    except AttributeError as e:
        app.logger.error(f"AttributeError in process_resume: {str(e)}")
        return jsonify({"error": "An error occurred with user data. Please log in again."}), 401
    except Exception as e:
        app.logger.error(f"Error in process_resume: {str(e)}")
        return jsonify({"error": "An unexpected error occurred. Please try again later."}), 500

@app.errorhandler(404)
def not_found_error(error):
    app.logger.error(f"404 error: {str(error)}")
    return jsonify({"error": "Not Found"}), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"500 error: {str(error)}")
    return jsonify({"error": "Internal Server Error"}), 500

@app.before_request
def check_user_session():
    if current_user.is_authenticated:
        user = User.query.get(current_user.id)
        if user is None:
            logout_user()
        else:
            login_user(user)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)