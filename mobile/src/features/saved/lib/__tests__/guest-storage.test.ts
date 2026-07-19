import { File } from "expo-file-system";
import { readGuestSaved, writeGuestSaved } from "@/features/saved/lib/guest-storage";
import type { SpotCard } from "@/lib/api-types";

const spot = (id: string): SpotCard => ({
  contentId: id,
  title: id,
  firstImageUrl: null,
  category: null,
});

describe("guest-storage", () => {
  beforeEach(() => jest.clearAllMocks());

  it("returns [] when the file does not exist", async () => {
    (File as unknown as jest.Mock).mockImplementation(() => ({ exists: false }));
    expect(await readGuestSaved()).toEqual([]);
  });

  it("parses the persisted list", async () => {
    const spots = [spot("a")];
    (File as unknown as jest.Mock).mockImplementation(() => ({
      exists: true,
      text: jest.fn().mockResolvedValue(JSON.stringify(spots)),
    }));
    expect(await readGuestSaved()).toEqual(spots);
  });

  it("returns [] when the persisted content is not an array", async () => {
    (File as unknown as jest.Mock).mockImplementation(() => ({
      exists: true,
      text: jest.fn().mockResolvedValue(JSON.stringify({ not: "an array" })),
    }));
    expect(await readGuestSaved()).toEqual([]);
  });

  it("returns [] when the filesystem throws", async () => {
    (File as unknown as jest.Mock).mockImplementation(() => {
      throw new Error("no fs");
    });
    expect(await readGuestSaved()).toEqual([]);
  });

  it("creates then writes when the file is new", async () => {
    const create = jest.fn();
    const write = jest.fn();
    (File as unknown as jest.Mock).mockImplementation(() => ({ exists: false, create, write }));
    await writeGuestSaved([spot("a")]);
    expect(create).toHaveBeenCalled();
    expect(write).toHaveBeenCalledWith(JSON.stringify([spot("a")]));
  });

  it("writes without creating when the file already exists", async () => {
    const create = jest.fn();
    const write = jest.fn();
    (File as unknown as jest.Mock).mockImplementation(() => ({ exists: true, create, write }));
    await writeGuestSaved([]);
    expect(create).not.toHaveBeenCalled();
    expect(write).toHaveBeenCalledWith("[]");
  });

  it("never throws when the filesystem is unavailable", async () => {
    (File as unknown as jest.Mock).mockImplementation(() => {
      throw new Error("no fs");
    });
    await expect(writeGuestSaved([])).resolves.toBeUndefined();
  });
});
