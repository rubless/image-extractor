import sys
import os
import shutil
import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QFileDialog,
    QMessageBox, QSpinBox, QCheckBox
)
from PyQt5.QtCore import Qt

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# 지원하는 이미지 확장자
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"}


class ImageExtractor(QWidget):
    def __init__(self):
        super().__init__()
        self.output_folder = ""
        self.total_extracted = 0  # Initialize total_extracted here
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("이미지 추출기")
        self.setFixedSize(600, 550)
        self.setAcceptDrops(True)

        layout = QVBoxLayout()

        # ── 저장 폴더 선택 ──
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("저장할 폴더 경로를 선택하세요...")
        self.folder_input.setReadOnly(True)

        folder_btn = QPushButton("폴더 선택")
        folder_btn.clicked.connect(self.select_folder)

        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(folder_btn)
        layout.addLayout(folder_layout)

        # ── 수량 제한 설정 ──
        limit_layout = QHBoxLayout()

        self.limit_check = QCheckBox("폴더당 이미지 수량 제한")
        self.limit_check.toggled.connect(self.on_limit_toggled)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 9999)
        self.limit_spin.setValue(1)
        self.limit_spin.setSuffix("장")
        self.limit_spin.setEnabled(False)

        self.limit_label = QLabel("(최신순으로 선택)")
        self.limit_label.setStyleSheet("color: #888;")
        self.limit_label.setEnabled(False)

        limit_layout.addWidget(self.limit_check)
        limit_layout.addWidget(self.limit_spin)
        limit_layout.addWidget(self.limit_label)
        limit_layout.addStretch()
        layout.addLayout(limit_layout)

        # ── 드래그 앤 드롭 안내 ──
        self.drop_label = QLabel("여기에 폴더를 드래그 앤 드롭하세요")
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setFixedHeight(100)
        self.drop_label.setStyleSheet(
            "border: 2px dashed #aaa; font-size: 14px; color: #555;"
        )
        layout.addWidget(self.drop_label)

        # ── 통계 라벨 ──
        self.stats_label = QLabel("추출된 이미지: 0장")
        self.stats_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #2a7ad5;")
        layout.addWidget(self.stats_label)

        # ── 처리 로그 ──
        self.log_list = QListWidget()
        layout.addWidget(self.log_list)

        self.setLayout(layout)

    # ── 체크박스 토글 ──
    def on_limit_toggled(self, checked):
        self.limit_spin.setEnabled(checked)
        self.limit_label.setEnabled(checked)

    # ── 폴더 선택 ──
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "저장 폴더 선택")
        if folder:
            self.output_folder = folder
            self.folder_input.setText(folder)
            logging.info(f"저장 폴더 설정: {folder}")

    # ── 단일 폴더에서 이미지 찾기 (해당 폴더만) ──
    def find_images_in_folder(self, folder_path):
        """해당 폴더(직속)에 있는 이미지 파일만 반환."""
        images = []
        try:
            # Ensure the path is a directory before listing its contents
            if not os.path.isdir(folder_path):
                return []

            for f in os.listdir(folder_path):
                full = os.path.join(folder_path, f)
                if os.path.isfile(full):
                    _, ext = os.path.splitext(f)
                    if ext.lower() in SUPPORTED_EXTENSIONS:
                        images.append(full)
        except PermissionError:
            self.log_list.addItem(f"⚠️ 접근 권한 없음: {folder_path}")
            logging.warning(f"Permission denied for folder: {folder_path}")
        except Exception as e:
            self.log_list.addItem(f"❌ 폴더 탐색 오류: {folder_path} ({e})")
            logging.error(f"Error listing directory {folder_path}: {e}")
        return images

    # ── 모든 하위 폴더 찾기 (재귀) ──
    def find_all_subfolders(self, folder_path):
        """자기 자신 포함, 모든 하위 폴더 목록 반환."""
        folders = []
        try:
            # Ensure the path is a directory before walking it
            if not os.path.isdir(folder_path):
                return []

            for root, dirs, files in os.walk(folder_path):
                folders.append(root)
        except PermissionError:
            self.log_list.addItem(f"⚠️ 접근 권한 없음: {folder_path} (하위 폴더 탐색 중)")
            logging.warning(f"Permission denied for folder during walk: {folder_path}")
        except Exception as e:
            self.log_list.addItem(f"❌ 하위 폴더 탐색 오류: {folder_path} ({e})")
            logging.error(f"Error walking directory {folder_path}: {e}")
        return folders

    # ── 최신순 정렬 후 수량 제한 ──
    def apply_limit(self, images):
        """수정 시간 기준 최신순 정렬 → 수량 제한 적용."""
        # Ensure all paths are valid files before getting modification time
        valid_images = [img for img in images if os.path.isfile(img)]

        # 최신순 정렬 (수정 시간 내림차순)
        try:
            valid_images.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        except OSError as e:
            self.log_list.addItem(f"❌ 파일 수정 시간 접근 오류: {e}")
            logging.error(f"Error accessing file modification time: {e}")
            return [] # Return empty list if sorting fails

        if self.limit_check.isChecked():
            limit = self.limit_spin.value()
            return valid_images[:limit]
        return valid_images

    # ── 중복 파일명 처리 ──
    def get_unique_path(self, dest_path):
        if not os.path.exists(dest_path):
            return dest_path
        name, ext = os.path.splitext(dest_path)
        counter = 2
        while True:
            new_path = f"{name} ({counter}){ext}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1

    # ── 드래그 진입 ──
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_label.setStyleSheet(
                "border: 2px dashed #2a7ad5; font-size: 14px; color: #2a7ad5; background-color: #e8f0fe;"
            )

    # ── 드래그 이탈 ──
    def dragLeaveEvent(self, event):
        self.drop_label.setStyleSheet(
            "border: 2px dashed #aaa; font-size: 14px; color: #555;"
        )

    # ── 드롭 처리 ──
    def dropEvent(self, event):
        self.drop_label.setStyleSheet(
            "border: 2px dashed #aaa; font-size: 14px; color: #555;"
        )

        if not self.output_folder:
            QMessageBox.warning(self, "경고", "먼저 저장할 폴더를 선택하세요.")
            return

        urls = event.mimeData().urls()
        batch_count = 0
        limit_text = f" (폴더당 {self.limit_spin.value()}장)" if self.limit_check.isChecked() else " (전체)"

        for url in urls:
            path = url.toLocalFile()

            # Ensure the path is valid before proceeding
            if not os.path.exists(path):
                self.log_list.addItem(f"⚠️ 존재하지 않는 경로: {path}")
                logging.warning(f"Dropped path does not exist: {path}")
                continue

            # 폴더인 경우
            if os.path.isdir(path):
                folder_name = os.path.basename(path)
                self.log_list.addItem(f"── 📁 {folder_name} 탐색{limit_text} ──")

                # 모든 하위 폴더를 개별 처리
                subfolders = self.find_all_subfolders(path)

                for sub in subfolders:
                    images = self.find_images_in_folder(sub)
                    if not images:
                        continue

                    # 수량 제한 적용
                    selected = self.apply_limit(images)

                    # 상대 경로 표시
                    rel = os.path.relpath(sub, path)
                    if rel == ".":
                        rel = folder_name
                    self.log_list.addItem(f"  📂 {rel}: {len(selected)}/{len(images)}장 선택")

                    for img_path in selected:
                        if self.copy_image(img_path):
                            batch_count += 1

            # 파일인 경우
            elif os.path.isfile(path):
                _, ext = os.path.splitext(path)
                if ext.lower() in SUPPORTED_EXTENSIONS:
                    if self.copy_image(path):
                        batch_count += 1
                else:
                    self.log_list.addItem(f"⚠️ 지원하지 않는 형식: {os.path.basename(path)}")

        # 결과 요약
        self.total_extracted += batch_count
        self.stats_label.setText(f"추출된 이미지: 총 {self.total_extracted}장")
        self.log_list.addItem(f"── ✅ 이번 작업: {batch_count}장 복사 완료 ──")
        self.log_list.addItem("")
        self.log_list.scrollToBottom()

    # ── 이미지 복사 ──
    def copy_image(self, src_path):
        # Ensure source path is a file before attempting to copy
        if not os.path.isfile(src_path):
            self.log_list.addItem(f"❌ 원본 파일이 존재하지 않음: {src_path}")
            logging.error(f"Source file does not exist: {src_path}")
            return False

        file_name = os.path.basename(src_path)
        dest_path = os.path.join(self.output_folder, file_name)
        dest_path = self.get_unique_path(dest_path)

        try:
            shutil.copy2(src_path, dest_path)
            new_name = os.path.basename(dest_path)
            msg = f"    ✅ {file_name}" + (f" → {new_name}" if new_name != file_name else "")
            self.log_list.addItem(msg)
            logging.info(f"복사: {src_path} → {dest_path}")
            return True
        except PermissionError:
            self.log_list.addItem(f"    ❌ 쓰기 권한 없음: {self.output_folder}")
            logging.error(f"Permission denied to write to: {self.output_folder}")
            return False
        except Exception as e:
            self.log_list.addItem(f"    ❌ 복사 실패: {file_name} ({e})")
            logging.error(f"Failed to copy {src_path} to {dest_path}: {e}")
            return False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageExtractor()
    window.show()
    sys.exit(app.exec_())
