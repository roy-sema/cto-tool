export function avatarTitle(name: string): string {
  const words = name.trim().toLocaleUpperCase().split(" ");
  let title = words[0].charAt(0);
  if (words.length > 1) title += words[words.length - 1].charAt(0);
  return title;
}

export function toHumanReadableDate(date: number | undefined | null, timezone?: string): string {
  if (!date) return "No data";

  return new Date(date * 1000).toLocaleString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "numeric",
    hour12: true,
    timeZone: timezone,
  });
}
