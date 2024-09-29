import sys
import os
import json
import keyring
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QMessageBox, QProgressBar, QCheckBox, QComboBox)
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from openai import OpenAI

CONFIG_DIR = os.path.expanduser("~/.config/prompt_runner")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
KEYRING_SERVICE = "prompt_runner"
KEYRING_USERNAME = "openai_api_key"

class PromptRunner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.load_settings()

    def initUI(self):
        self.setWindowTitle('Enhanced Prompt Runner')
        self.setGeometry(100, 100, 800, 600)
        self.setWindowIcon(QIcon('logo.png'))

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)

        # Title Input
        title_layout = QHBoxLayout()
        title_label = QLabel('Title:')
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText('Enter a title for your prompt')
        title_layout.addWidget(title_label)
        title_layout.addWidget(self.title_input)
        main_layout.addLayout(title_layout)

        # Prompt Input
        prompt_label = QLabel('Prompt:')
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText('Enter your prompt here...')
        self.prompt_input.textChanged.connect(self.update_char_count)
        main_layout.addWidget(prompt_label)
        main_layout.addWidget(self.prompt_input)

        # Character Count
        self.char_count_label = QLabel('Characters: 0')
        main_layout.addWidget(self.char_count_label)

        # Folder Configuration
        folder_layout = QVBoxLayout()
        self.prompts_folder = self.create_folder_input('Prompts Folder:', 'Select folder to store prompts')
        self.outputs_folder = self.create_folder_input('Outputs Folder:', 'Select folder to store outputs')
        folder_layout.addLayout(self.prompts_folder)
        folder_layout.addLayout(self.outputs_folder)
        main_layout.addLayout(folder_layout)

        # API Key Management
        api_layout = QHBoxLayout()
        api_label = QLabel('OpenAI API Key:')
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_api_key = QCheckBox('Show')
        self.show_api_key.stateChanged.connect(self.toggle_api_key_visibility)
        test_api_button = QPushButton('Test API Key')
        test_api_button.clicked.connect(self.test_api_key)
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_key_input)
        api_layout.addWidget(self.show_api_key)
        api_layout.addWidget(test_api_button)
        main_layout.addLayout(api_layout)

        # Model Selection
        model_layout = QHBoxLayout()
        model_label = QLabel('Model:')
        self.model_selector = QComboBox()
        self.model_selector.addItems(['gpt-3.5-turbo', 'gpt-4'])
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_selector)
        main_layout.addLayout(model_layout)

        # Run Button
        self.run_button = QPushButton('Run Prompt')
        self.run_button.clicked.connect(self.run_prompt)
        main_layout.addWidget(self.run_button)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Terminal Output
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFont(QFont('Courier', 10))
        main_layout.addWidget(self.terminal_output)

        # Dark Mode Toggle
        self.dark_mode_toggle = QCheckBox('Dark Mode')
        self.dark_mode_toggle.stateChanged.connect(self.toggle_dark_mode)
        main_layout.addWidget(self.dark_mode_toggle)

        # Save Configuration Button
        save_config_button = QPushButton('Save Configuration')
        save_config_button.clicked.connect(self.save_settings)
        main_layout.addWidget(save_config_button)

        # Reset to Default
        reset_button = QPushButton('Reset to Default')
        reset_button.clicked.connect(self.reset_to_default)
        main_layout.addWidget(reset_button)

    def create_folder_input(self, label_text, tooltip):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        input_field = QLineEdit()
        input_field.setToolTip(tooltip)
        browse_button = QPushButton('Browse')
        browse_button.clicked.connect(lambda: self.browse_folder(input_field))
        layout.addWidget(label)
        layout.addWidget(input_field)
        layout.addWidget(browse_button)
        return layout

    def browse_folder(self, input_field):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if folder:
            input_field.setText(folder)

    def update_char_count(self):
        count = len(self.prompt_input.toPlainText())
        self.char_count_label.setText(f'Characters: {count}')

    def toggle_api_key_visibility(self, state):
        if state == Qt.CheckState.Checked.value:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

    def test_api_key(self):
        api_key = self.api_key_input.text()
        client = OpenAI(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello, World!"}],
                max_tokens=5
            )
            QMessageBox.information(self, 'API Key Test', 'API key is valid!')
        except Exception as e:
            QMessageBox.warning(self, 'API Key Test', f'API key is invalid: {str(e)}')

    def run_prompt(self):
        prompt = self.prompt_input.toPlainText()
        if not prompt:
            QMessageBox.warning(self, 'Error', 'Please enter a prompt.')
            return

        self.progress_bar.setVisible(True)
        self.run_button.setEnabled(False)
        self.terminal_output.clear()

        self.worker = PromptWorker(prompt, self.api_key_input.text(), self.model_selector.currentText())
        self.worker.update_progress.connect(self.update_progress)
        self.worker.update_output.connect(self.update_output)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_output(self, text):
        if not text.startswith("API Response:"):
            self.terminal_output.append(text)
        else:
            self.terminal_output.clear()  # Clear previous status messages
            self.terminal_output.append(text.replace("API Response:", "").strip())

    def on_worker_finished(self):
        self.progress_bar.setVisible(False)
        self.run_button.setEnabled(True)
        self.save_prompt_and_output()

    def sanitize_filename(self, title):
        # Remove any characters that aren't alphanumeric, space, or underscore
        sanitized = ''.join(c for c in title if c.isalnum() or c in (' ', '_'))
        # Capitalize each word
        prettified = ' '.join(word.capitalize() for word in sanitized.split())
        return prettified

    def save_prompt_and_output(self):
        title = self.title_input.text() or 'Untitled'
        prompt = self.prompt_input.toPlainText()
        output = self.terminal_output.toPlainText()
        prompts_folder = self.prompts_folder.itemAt(1).widget().text()
        outputs_folder = self.outputs_folder.itemAt(1).widget().text()

        if not os.path.exists(prompts_folder):
            os.makedirs(prompts_folder)
        if not os.path.exists(outputs_folder):
            os.makedirs(outputs_folder)

        filename = self.sanitize_filename(title)
        prompt_file = os.path.join(prompts_folder, f'{filename}.md')
        output_file = os.path.join(outputs_folder, f'{filename}.md')

        if os.path.exists(prompt_file) or os.path.exists(output_file):
            reply = QMessageBox.question(self, 'File Exists', 'Files with this title already exist. Overwrite?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

        # Save prompt as markdown
        with open(prompt_file, 'w') as f:
            f.write(prompt)

        # Save output as markdown
        with open(output_file, 'w') as f:
            f.write(output)

        QMessageBox.information(self, 'Success', 'Prompt and output saved successfully as markdown files!')

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                settings = json.load(f)
            self.prompts_folder.itemAt(1).widget().setText(settings.get('prompts_folder', ''))
            self.outputs_folder.itemAt(1).widget().setText(settings.get('outputs_folder', ''))
            self.dark_mode_toggle.setChecked(settings.get('dark_mode', False))
            self.model_selector.setCurrentText(settings.get('model', 'gpt-3.5-turbo'))

        # Load API key from keyring
        api_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if api_key:
            self.api_key_input.setText(api_key)
        else:
            os.makedirs(CONFIG_DIR, exist_ok=True)

    def save_settings(self):
        settings = {
            'prompts_folder': self.prompts_folder.itemAt(1).widget().text(),
            'outputs_folder': self.outputs_folder.itemAt(1).widget().text(),
            'dark_mode': self.dark_mode_toggle.isChecked(),
            'model': self.model_selector.currentText()
        }
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(settings, f)

        # Save API key to keyring
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, self.api_key_input.text())

        QMessageBox.information(self, 'Configuration Saved', f'Configuration has been saved successfully!')

    def toggle_dark_mode(self, state):
        if state == Qt.CheckState.Checked.value:
            self.setStyleSheet("""
                QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QLineEdit, QTextEdit {
                    background-color: #3b3b3b;
                    border: 1px solid #5b5b5b;
                }
                QPushButton {
                    background-color: #4b4b4b;
                    border: 1px solid #5b5b5b;
                }
                QPushButton:hover {
                    background-color: #5b5b5b;
                }
            """)
        else:
            self.setStyleSheet("")

    def reset_to_default(self):
        self.prompt_input.clear()
        self.title_input.clear()
        self.prompts_folder.itemAt(1).widget().clear()
        self.outputs_folder.itemAt(1).widget().clear()
        self.api_key_input.clear()
        self.terminal_output.clear()
        self.dark_mode_toggle.setChecked(False)
        self.model_selector.setCurrentIndex(0)

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

class PromptWorker(QThread):
    update_progress = pyqtSignal(int)
    update_output = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, prompt, api_key, model):
        super().__init__()
        self.prompt = prompt
        self.api_key = api_key
        self.model = model

    def run(self):
        client = OpenAI(api_key=self.api_key)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": self.prompt}
                ]
            )

            self.update_output.emit("API Response:")
            self.update_output.emit(response.choices[0].message.content.strip())
            self.update_progress.emit(100)
        except Exception as e:
            self.update_output.emit(f"Error: {str(e)}")
        finally:
            self.finished.emit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PromptRunner()
    ex.show()
    sys.exit(app.exec())