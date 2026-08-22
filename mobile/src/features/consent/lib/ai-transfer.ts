/** 문구는 개인정보처리방침 제6조(국외 이전) 표와 같은 사실을 말해야 한다 — 한쪽만 고치지 않는다. */
export const AI_TRANSFER = {
  rowTitle: "[선택] AI 질문 처리",
  rowOn: "사용 중",
  rowOff: "끔",
  rowSub:
    "자유 입력 질문을 DeepSeek(중국)으로 보내 검색 조건을 뽑아요. 사진·위치·계정 정보는 보내지 않아요.",
  offNotice: "AI 질문을 꺼두셨어요. 사진으로 찾기는 그대로 쓸 수 있어요.",
  offAction: "켜기",
  offToast: "AI 질문이 꺼져 있어요. 마이 › 동의 내역에서 켤 수 있어요",
  onboardingNote:
    "여행 탭에서 자유 입력으로 물어보면 질문 문장이 국외 AI(DeepSeek)로 전달돼요. 사진과 위치는 전달하지 않으며, [마이 > 동의 내역]에서 끌 수 있어요.",
} as const;
