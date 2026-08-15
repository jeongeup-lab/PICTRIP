export const AI_CONSENT = {
  title: "질문은 Google Gemini로 전달돼요",
  body: "입력하신 질문 텍스트가 의도를 파악하기 위해 Google LLC의 Gemini API로 전송됩니다. 여행지 검색 자체는 PICTRIP 서버에서 처리해요.",
  scope: "첨부한 사진은 Gemini로 전송되지 않아요.",
  fallback: "동의하지 않아도 사진으로 찾기와 둘러보기는 그대로 이용할 수 있어요.",
  policyLabel: "개인정보처리방침에서 국외 이전 안내 보기",
  agreeLabel: "동의하고 질문하기",
  declineLabel: "동의 안 함",
  declined: "동의하지 않아 질문을 보내지 않았어요",
} as const;
