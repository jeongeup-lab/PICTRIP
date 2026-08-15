import { isDistanceTag, metricOf } from "@/features/travel/lib/metric";

describe("isDistanceTag", () => {
  it.each(["2.4km", "870m", "40m", "10m", "1.0km", "12km"])("거리 태그를 알아본다: %s", (tag) => {
    expect(isDistanceTag(tag)).toBe(true);
  });

  it.each(["한산", "하위 8%", "D-3", null, undefined])("거리가 아닌 것: %s", (tag) => {
    expect(isDistanceTag(tag)).toBe(false);
  });
});

describe("metricOf", () => {
  it("거리 태그는 칩이 되지 않는다 — 지역 줄이 이미 말한다", () => {
    expect(metricOf("2.4km", "직선거리 기준")).toBeNull();
  });

  it.each(["870m", "40m", "10m"])("미터 태그도 칩이 아니라 거리다: %s", (tag) => {
    expect(metricOf(tag, "직선거리 기준")).toBeNull();
  });

  it("혼잡도 태그는 사람 아이콘과 예측 근거를 든다", () => {
    expect(metricOf("한산", "혼잡도 8/3 예측 기준")).toEqual({
      icon: "users",
      label: "한산",
      tooltip: "혼잡도 8/3 예측 기준",
    });
  });

  it("백분위 태그도 혼잡도로 읽는다", () => {
    expect(metricOf("하위 8%", "혼잡도 예측 기준")?.icon).toBe("users");
  });

  it("사진 유사도는 이미지 아이콘을 쓰고 서버 문구를 그대로 든다", () => {
    expect(metricOf("유사도 87%", "사진 유사도 기준")).toEqual({
      icon: "image",
      label: "유사도 87%",
      tooltip: "사진 유사도 기준",
    });
  });

  it("축제 디데이는 달력 아이콘을 쓰고 근거 줄이 없다", () => {
    expect(metricOf("D-3", null)).toEqual({
      icon: "calendar",
      label: "D-3",
      tooltip: "축제 기간 기준",
    });
  });

  it("태그가 없으면 칩도 없다", () => {
    expect(metricOf(null, "직선거리 기준")).toBeNull();
    expect(metricOf("", null)).toBeNull();
  });

  it("모르는 태그는 근거 없이 중립 아이콘으로 낸다", () => {
    expect(metricOf("바다뷰", null)).toEqual({
      icon: "tag",
      label: "바다뷰",
      tooltip: "",
    });
  });
});
