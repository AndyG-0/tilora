// Timezone-aware wall-clock components, shared by the non-digital clock
// faces (analog hands, binary dots, word-clock phrase) which all need
// discrete hour/minute/second integers rather than a formatted string.
export interface WallTime {
	hours: number;
	minutes: number;
	seconds: number;
}

export function wallTime(date: Date, timeZone: string): WallTime {
	const parts = new Intl.DateTimeFormat('en-US', {
		timeZone,
		hourCycle: 'h23',
		hour: 'numeric',
		minute: 'numeric',
		second: 'numeric',
	}).formatToParts(date);

	const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);

	return { hours: get('hour'), minutes: get('minute'), seconds: get('second') };
}

const HOUR_NAMES = ['twelve', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven'];

// Rounds to the nearest 5 minutes, e.g. "ten past three", "quarter to four",
// "half past three", "three o'clock". Standard word-clock phrasing doesn't
// distinguish AM/PM, so noon/midnight get their own words instead of "zero
// o'clock" or "twelve o'clock" twice a day.
export function wordPhrase(hours: number, minutes: number): string {
	const roundedMinutes = Math.round(minutes / 5) * 5;
	const hour12 = hours % 12;

	if (roundedMinutes === 0) {
		if (hours === 0) return 'midnight';
		if (hours === 12) return 'noon';
		return `${HOUR_NAMES[hour12]} o'clock`;
	}

	if (roundedMinutes === 60) {
		const nextHour = (hour12 + 1) % 12;
		return `${HOUR_NAMES[nextHour]} o'clock`;
	}

	const pastPhrases: Record<number, string> = {
		5: 'five past',
		10: 'ten past',
		15: 'quarter past',
		20: 'twenty past',
		25: 'twenty-five past',
		30: 'half past',
	};
	const toPhrases: Record<number, string> = {
		35: 'twenty-five to',
		40: 'twenty to',
		45: 'quarter to',
		50: 'ten to',
		55: 'five to',
	};

	if (roundedMinutes in pastPhrases) {
		return `${pastPhrases[roundedMinutes]} ${HOUR_NAMES[hour12]}`;
	}

	const nextHour = (hour12 + 1) % 12;
	return `${toPhrases[roundedMinutes]} ${HOUR_NAMES[nextHour]}`;
}
