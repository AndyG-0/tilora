// Maps an ICAO airline code (the callsign's 3-letter prefix, e.g. "UAL")
// to its bundled pixel-badge asset. These are small, genuinely low-resolution
// source bitmaps (not scaled-down SVGs) so `image-rendering: pixelated` in
// FlightsTile/FlightsDetail/FlightsScreensaver actually blocks up into the
// LED-sign look rather than anti-aliasing smooth. Airlines outside this set
// fall back to a plain text badge showing their raw ICAO code.

import aal from './assets/airlines/aal.png';
import aar from './assets/airlines/aar.png';
import aay from './assets/airlines/aay.png';
import abx from './assets/airlines/abx.png';
import aca from './assets/airlines/aca.png';
import afr from './assets/airlines/afr.png';
import ana from './assets/airlines/ana.png';
import asa from './assets/airlines/asa.png';
import atn from './assets/airlines/atn.png';
import baw from './assets/airlines/baw.png';
import cpa from './assets/airlines/cpa.png';
import dal from './assets/airlines/dal.png';
import dlh from './assets/airlines/dlh.png';
import edv from './assets/airlines/edv.png';
import ein from './assets/airlines/ein.png';
import eny from './assets/airlines/eny.png';
import fdx from './assets/airlines/fdx.png';
import fft from './assets/airlines/fft.png';
import hal from './assets/airlines/hal.png';
import ibe from './assets/airlines/ibe.png';
import jal from './assets/airlines/jal.png';
import jbu from './assets/airlines/jbu.png';
import jia from './assets/airlines/jia.png';
import klm from './assets/airlines/klm.png';
import nks from './assets/airlines/nks.png';
import qfa from './assets/airlines/qfa.png';
import qxe from './assets/airlines/qxe.png';
import rpa from './assets/airlines/rpa.png';
import sas from './assets/airlines/sas.png';
import skw from './assets/airlines/skw.png';
import swa from './assets/airlines/swa.png';
import tap from './assets/airlines/tap.png';
import ual from './assets/airlines/ual.png';
import ups from './assets/airlines/ups.png';
import vir from './assets/airlines/vir.png';

const AIRLINE_LOGOS: Record<string, string> = {
	AAL: aal,
	AAR: aar,
	AAY: aay,
	ABX: abx,
	ACA: aca,
	AFR: afr,
	ANA: ana,
	ASA: asa,
	ATN: atn,
	BAW: baw,
	CPA: cpa,
	DAL: dal,
	DLH: dlh,
	EDV: edv,
	EIN: ein,
	ENY: eny,
	FDX: fdx,
	FFT: fft,
	HAL: hal,
	IBE: ibe,
	JAL: jal,
	JBU: jbu,
	JIA: jia,
	KLM: klm,
	NKS: nks,
	QFA: qfa,
	QXE: qxe,
	RPA: rpa,
	SAS: sas,
	SKW: skw,
	SWA: swa,
	TAP: tap,
	UAL: ual,
	UPS: ups,
	VIR: vir,
};

export function airlineLogoSrc(code: string | null): string | null {
	if (!code) return null;
	return AIRLINE_LOGOS[code] ?? null;
}
