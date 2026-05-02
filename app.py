import os
import json
import threading
import websocket
import webbrowser
from threading import Timer
from flask import Flask, render_template
from flask_sock import Sock
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

app = Flask(__name__)
sock = Sock(app)

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
# ---------------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@sock.route('/listen')
def listen(ws):
    print("\n🔌 웹 마이크 연결됨! 딥그램으로 소리 전송을 시작합니다.")
    
    # 에러 유발 가능성이 있는 부분 수정했습니다.
    dg_url = "wss://api.deepgram.com/v1/listen?model=nova-2&language=ko&smart_format=true&encoding=linear16&sample_rate=16000&channels=1"

    
    def on_message(dg_ws, message):
        try:
            data = json.loads(message)
            if "channel" in data:
                sentence = data["channel"]["alternatives"][0]["transcript"]
                if sentence.strip():
                    if not data.get("is_final"):
                        print(f"👂 듣는 중... {sentence}", end="\r")
                    
                    if data.get("is_final"):
                        print(f"\n✅ [인식 완료] {sentence}")
                        
                        # 각 언어별 번역 결과를 담을 딕셔너리
                        results = {"ko": sentence}
                        threads = []

                        # 번역을 수행할 개별 함수
                        def translate_and_store(lang_key, target_code):
                            try:
                                results[lang_key] = GoogleTranslator(source='ko', target=target_code).translate(sentence)
                            except Exception as e:
                                results[lang_key] = f"Error: {e}"

                        # 번역할 언어 설정 (키값: 대상언어코드)
                        target_languages = {
                            "en": "en",
                            "vi": "vi",
                            "id": "id",
                            "ny": "ny"
                        }

                        # 1. 각 언어별로 번역 스레드 생성 및 시작
                        for key, code in target_languages.items():
                            t = threading.Thread(target=translate_and_store, args=(key, code))
                            t.start()
                            threads.append(t)

                        # 2. 모든 번역 작업이 끝날 때까지 대기
                        for t in threads:
                            t.join()

                        # 3. 모든 번역이 완료된 후 한꺼번에 웹으로 전송
                        ws.send(json.dumps(results))
                        print(f"⚡ [병렬 번역 완료] 모든 언어 전송 성공")

        except Exception as e:
            print(f"⚠️ 처리 에러: {e}")

    def on_error(dg_ws, error):
        # [적용] 에러 상세 내역 출력 추가
        print(f"\n❌ [딥그램 에러] {error}")
        if hasattr(error, 'status_code'):
            print(f"Status Code: {error.status_code}")

    def on_close(dg_ws, close_status_code, close_msg):
        print(f"\n🔌 딥그램 연결이 종료되었습니다. (코드: {close_status_code})")

    def on_open(dg_ws):
        print("🚀 딥그램 엔진 가동 시작! (말씀을 시작해 보세요)\n")
        def run():
            try:
                while True:
                    audio_data = ws.receive()
                    if audio_data:
                        dg_ws.send(audio_data, opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception as e:
                print(f"⚠️ [클라이언트 웹소켓 에러] {e}")
                dg_ws.close()
        threading.Thread(target=run, daemon=True).start()

    dg_ws = websocket.WebSocketApp(
        dg_url,
        header=[f"Authorization: Token {DEEPGRAM_API_KEY}"],
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    dg_ws.run_forever()

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    # Render와 같은 플랫폼은 PORT 환경변수를 사용합니다.
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)