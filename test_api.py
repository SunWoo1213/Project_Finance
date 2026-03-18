import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 1. .env 파일에서 환경 변수 불러오기
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key or api_key == "sk-...":
    print("❌ 에러: .env 파일에 OPENAI_API_KEY가 제대로 설정되지 않았습니다.")
    exit()

print("✅ API 키 로드 성공! OpenAI에 연결을 시도합니다...")

try:
    # 2. Langchain을 통해 OpenAI 모델 세팅 (가장 저렴하고 빠른 gpt-4o-mini 사용)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    
    # 3. 아주 간단한 질문 던지기
    response = llm.invoke("안녕? 넌 누구니? 딱 한 문장으로 대답해줘.")
    
    # 4. 결과 출력
    print("\n🎉 [테스트 성공! OpenAI의 답변입니다]")
    print(f"🤖 AI: {response.content}")

except Exception as e:
    print(f"\n❌ [테스트 실패] OpenAI 통신 중 에러가 발생했습니다:\n{e}")
    print("\n💡 팁: API 키가 올바른지, 또는 OpenAI 계정에 크레딧(잔액)이 남아있는지 확인해 주세요.")