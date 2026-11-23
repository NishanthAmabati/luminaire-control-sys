export interface TimeParts {
  hour: string;
  minute: string;
}

const pad = (value: number) => String(value).padStart(2, '0');

export const parse24Time = (value: string | undefined): TimeParts | null => {
  if (!value) return null;
  const [rawHour, rawMinute] = value.split(':');
  if (!rawHour || !rawMinute) return null;

  const hour = Number(rawHour);
  const minute = Number(rawMinute);
  if (!Number.isInteger(hour) || !Number.isInteger(minute)) return null;
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;

  return { hour: pad(hour), minute: pad(minute) };
};

export const formatTime = (hour: string, minute: string): string => {
  const parsed = parse24Time(hour && minute ? `${hour}:${minute}` : '');
  return parsed ? `${parsed.hour}:${parsed.minute}` : 'Select';
};
