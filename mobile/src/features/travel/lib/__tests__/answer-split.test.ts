import type { AnswerPart } from "@/features/travel/api";
import { splitAnswer } from "@/features/travel/lib/answer-split";

const part = (text: string, emphasis = false): AnswerPart => ({ text, emphasis });

describe("splitAnswer", () => {
  it("첫 문장까지를 헤드라인으로 가른다", () => {
    const { lead, rest } = splitAnswer([
      part("혼잡도 "),
      part("하위 20%", true),
      part(" 안쪽으로만 골랐어요. 제주 동쪽으로 8곳이에요."),
    ]);

    expect(lead.map((p) => p.text).join("")).toBe("혼잡도 하위 20% 안쪽으로만 골랐어요.");
    expect(rest.map((p) => p.text).join("")).toBe("제주 동쪽으로 8곳이에요.");
  });

  it("헤드라인 안의 강조를 유지한다", () => {
    const { lead } = splitAnswer([
      part("혼잡도 "),
      part("하위 20%", true),
      part(" 안쪽이에요. 뒤."),
    ]);

    expect(lead.filter((p) => p.emphasis).map((p) => p.text)).toEqual(["하위 20%"]);
  });

  it("문장 부호가 없으면 전부 헤드라인이다", () => {
    const { lead, rest } = splitAnswer([part("아직 정보가 없어요")]);

    expect(lead.map((p) => p.text).join("")).toBe("아직 정보가 없어요");
    expect(rest).toEqual([]);
  });

  it("물음표·느낌표도 문장 끝으로 센다", () => {
    const { lead, rest } = splitAnswer([part("어디로 갈까요? 조건을 알려주세요.")]);

    expect(lead.map((p) => p.text).join("")).toBe("어디로 갈까요?");
    expect(rest.map((p) => p.text).join("")).toBe("조건을 알려주세요.");

    const bang = splitAnswer([part("좋아요! 뒤 문장이에요.")]);
    expect(bang.lead.map((p) => p.text).join("")).toBe("좋아요!");
    expect(bang.rest.map((p) => p.text).join("")).toBe("뒤 문장이에요.");
  });

  it("빈 입력에도 빈 두 조각을 준다", () => {
    expect(splitAnswer([])).toEqual({ lead: [], rest: [] });
  });

  it("문장 부호가 마지막 조각 끝에 있으면 보충이 비어 있다", () => {
    const { lead, rest } = splitAnswer([part("한 문장뿐이에요.")]);

    expect(lead.map((p) => p.text).join("")).toBe("한 문장뿐이에요.");
    expect(rest).toEqual([]);
  });

  it("보충 앞의 공백 조각을 버린다", () => {
    const { lead, rest } = splitAnswer([
      part("혼잡도 "),
      part("하위 20%", true),
      part(" 안쪽으로만 골랐어요."),
      part(" "),
      part("제주 동쪽으로 8곳이에요."),
    ]);

    expect(lead.map((p) => p.text).join("")).toBe("혼잡도 하위 20% 안쪽으로만 골랐어요.");
    expect(rest.map((p) => p.text).join("")).toBe("제주 동쪽으로 8곳이에요.");
  });

  it("공백뿐인 조각만 남으면 보충이 비어 있다", () => {
    const { rest } = splitAnswer([part("한 문장뿐이에요."), part("  ")]);

    expect(rest).toEqual([]);
  });

  it("소수점을 문장 끝으로 세지 않는다", () => {
    const { lead, rest } = splitAnswer([
      part("가장 가까운 곳이 "),
      part("2.4km", true),
      part("예요."),
      part(" "),
      part("조건에 맞는 곳으로 8곳이에요."),
    ]);

    expect(lead.map((p) => p.text).join("")).toBe("가장 가까운 곳이 2.4km예요.");
    expect(rest.map((p) => p.text).join("")).toBe("조건에 맞는 곳으로 8곳이에요.");
  });

  it("한 조각 안에 소수점과 문장 끝이 같이 있어도 문장 끝에서 가른다", () => {
    const { lead, rest } = splitAnswer([part("2.4km예요. 제주 동쪽으로 8곳이에요.")]);

    expect(lead.map((p) => p.text).join("")).toBe("2.4km예요.");
    expect(rest.map((p) => p.text).join("")).toBe("제주 동쪽으로 8곳이에요.");
  });

  it("구분 공백이 다음 조각 앞에 붙어 있어도 보충에서 걷어낸다", () => {
    const { lead, rest } = splitAnswer([
      part("가장 가까운 맛집이 "),
      part("0.4km", true),
      part(" 거리예요."),
      part(" 성산일출봉 주변으로 "),
      part("5곳이에요."),
    ]);

    expect(lead.map((p) => p.text).join("")).toBe("가장 가까운 맛집이 0.4km 거리예요.");
    expect(rest.map((p) => p.text).join("")).toBe("성산일출봉 주변으로 5곳이에요.");
  });
});
