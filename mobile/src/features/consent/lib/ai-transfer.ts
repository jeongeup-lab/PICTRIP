/**
 * 문구는 개인정보처리방침 제6조(국외 이전) 표와 같은 사실을 말해야 한다 — 한쪽만 고치지 않는다.
 * `items` 는 법 제28조의8 제2항 각 호다. 동의를 받으려면 이걸 **동의 버튼과 같은 화면에서**
 * 미리 알려야 하므로 접거나 링크 뒤로 보내지 않는다. 줄일 수 있는 건 표현이지 항목이 아니다.
 */
export const AI_TRANSFER_VERSION = "2026-08-22";

export const AI_TRANSFER = {
  version: AI_TRANSFER_VERSION,

  sheetTitle: "이 항목에 아직 동의하지 않으셨어요",
  sheetBody: "시작할 때 넘기신 항목이에요. 지금 동의하면 바로 물어볼 수 있어요.",
  rowLabel: "AI 질문 처리 (개인정보 국외 이전)",

  items: [
    {
      key: "who",
      label: "받는 곳",
      value: "항저우 딥시크 인공지능 기초기술연구 · 중국",
    },
    {
      key: "what",
      label: "보내는 것",
      value: "질문 문장, 직전 한 턴의 질문·답변 요약, 직전 검색 조건과 결과 관광지 이름, 요청 시각",
    },
    {
      key: "when",
      label: "언제",
      value: "질문을 보낼 때마다 PICTRIP 서버가 HTTPS 로 전송",
    },
    {
      key: "why",
      label: "왜",
      value: "검색 조건 추출과 답변 작성 · 보유 기간은 받는 곳 정책에 따름",
    },
  ],

  note: "첨부한 사진과 현재 위치, 계정 정보는 보내지 않아요. 동의하지 않아도 사진으로 찾기와 둘러보기는 그대로 쓸 수 있고, 동의 후에도 [마이 › 동의 내역]에서 철회할 수 있어요.",
  policyLabel: "처리방침 제6조 전문",

  agreeLabel: "동의하고 질문하기",
  declineLabel: "안 함",
  declined: "동의하지 않아 질문을 보내지 않았어요",

  rowTitle: "[선택] AI 질문 처리 (국외 이전)",
  rowOn: "동의함",
  rowOff: "동의 안 함",
  rowSub:
    "질문 문장을 국외 AI 사업자에게 보내 검색 조건을 뽑아요. 사진·위치·계정 정보는 보내지 않아요.",

  onboardingNote:
    "여행 탭에서 자유 입력으로 물어보면 질문 문장이 국외 AI 사업자에게 전달돼요. 처음 물어볼 때 동의를 받고, 사진과 위치는 전달하지 않아요.",
} as const;
