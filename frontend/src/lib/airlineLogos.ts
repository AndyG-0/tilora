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
import aic from './assets/airlines/aic.png';
import amx from './assets/airlines/amx.png';
import ana from './assets/airlines/ana.png';
import anz from './assets/airlines/anz.png';
import asa from './assets/airlines/asa.png';
import ash from './assets/airlines/ash.png';
import atn from './assets/airlines/atn.png';
import aua from './assets/airlines/aua.png';
import ava from './assets/airlines/ava.png';
import azu from './assets/airlines/azu.png';
import baw from './assets/airlines/baw.png';
import bel from './assets/airlines/bel.png';
import bos from './assets/airlines/bos.png';
import cal from './assets/airlines/cal.png';
import cca from './assets/airlines/cca.png';
import ces from './assets/airlines/ces.png';
import cks from './assets/airlines/cks.png';
import cmp from './assets/airlines/cmp.png';
import cpa from './assets/airlines/cpa.png';
import cpz from './assets/airlines/cpz.png';
import csn from './assets/airlines/csn.png';
import dal from './assets/airlines/dal.png';
import dlh from './assets/airlines/dlh.png';
import edv from './assets/airlines/edv.png';
import ein from './assets/airlines/ein.png';
import ely from './assets/airlines/ely.png';
import eny from './assets/airlines/eny.png';
import etd from './assets/airlines/etd.png';
import eth from './assets/airlines/eth.png';
import eva from './assets/airlines/eva.png';
import ewg from './assets/airlines/ewg.png';
import ezy from './assets/airlines/ezy.png';
import fdb from './assets/airlines/fdb.png';
import fdx from './assets/airlines/fdx.png';
import fft from './assets/airlines/fft.png';
import fin from './assets/airlines/fin.png';
import fji from './assets/airlines/fji.png';
import gec from './assets/airlines/gec.png';
import gia from './assets/airlines/gia.png';
import gjs from './assets/airlines/gjs.png';
import glo from './assets/airlines/glo.png';
import gti from './assets/airlines/gti.png';
import hal from './assets/airlines/hal.png';
import ibe from './assets/airlines/ibe.png';
import igo from './assets/airlines/igo.png';
import ity from './assets/airlines/ity.png';
import jal from './assets/airlines/jal.png';
import jbu from './assets/airlines/jbu.png';
import jia from './assets/airlines/jia.png';
import kal from './assets/airlines/kal.png';
import klm from './assets/airlines/klm.png';
import lan from './assets/airlines/lan.png';
import lot from './assets/airlines/lot.png';
import mas from './assets/airlines/mas.png';
import msr from './assets/airlines/msr.png';
import ncr from './assets/airlines/ncr.png';
import nks from './assets/airlines/nks.png';
import noz from './assets/airlines/noz.png';
import oae from './assets/airlines/oae.png';
import pac from './assets/airlines/pac.png';
import pdt from './assets/airlines/pdt.png';
import poe from './assets/airlines/poe.png';
import qfa from './assets/airlines/qfa.png';
import qtr from './assets/airlines/qtr.png';
import qxe from './assets/airlines/qxe.png';
import ram from './assets/airlines/ram.png';
import rou from './assets/airlines/rou.png';
import rpa from './assets/airlines/rpa.png';
import ryr from './assets/airlines/ryr.png';
import sas from './assets/airlines/sas.png';
import scx from './assets/airlines/scx.png';
import sia from './assets/airlines/sia.png';
import sil from './assets/airlines/sil.png';
import skw from './assets/airlines/skw.png';
import sli from './assets/airlines/sli.png';
import sva from './assets/airlines/sva.png';
import swa from './assets/airlines/swa.png';
import swr from './assets/airlines/swr.png';
import tam from './assets/airlines/tam.png';
import tap from './assets/airlines/tap.png';
import tha from './assets/airlines/tha.png';
import thy from './assets/airlines/thy.png';
import tsc from './assets/airlines/tsc.png';
import uae from './assets/airlines/uae.png';
import ual from './assets/airlines/ual.png';
import uca from './assets/airlines/uca.png';
import ups from './assets/airlines/ups.png';
import vir from './assets/airlines/vir.png';
import viv from './assets/airlines/viv.png';
import vlg from './assets/airlines/vlg.png';
import voi from './assets/airlines/voi.png';
import voz from './assets/airlines/voz.png';
import wgn from './assets/airlines/wgn.png';
import wja from './assets/airlines/wja.png';
import wzz from './assets/airlines/wzz.png';

const AIRLINE_LOGOS: Record<string, string> = {
	AAL: aal,
	AAR: aar,
	AAY: aay,
	ABX: abx,
	ACA: aca,
	AFR: afr,
	AIC: aic,
	AMX: amx,
	ANA: ana,
	ANZ: anz,
	ASA: asa,
	ASH: ash,
	ATN: atn,
	AUA: aua,
	AVA: ava,
	AZU: azu,
	BAW: baw,
	BEL: bel,
	BOS: bos,
	CAL: cal,
	CCA: cca,
	CES: ces,
	CKS: cks,
	CMP: cmp,
	CPA: cpa,
	CPZ: cpz,
	CSN: csn,
	DAL: dal,
	DLH: dlh,
	EDV: edv,
	EIN: ein,
	ELY: ely,
	ENY: eny,
	ETD: etd,
	ETH: eth,
	EVA: eva,
	EWG: ewg,
	EZY: ezy,
	FDB: fdb,
	FDX: fdx,
	FFT: fft,
	FIN: fin,
	FJI: fji,
	GEC: gec,
	GIA: gia,
	GJS: gjs,
	GLO: glo,
	GTI: gti,
	HAL: hal,
	IBE: ibe,
	IGO: igo,
	ITY: ity,
	JAL: jal,
	JBU: jbu,
	JIA: jia,
	KAL: kal,
	KLM: klm,
	LAN: lan,
	LOT: lot,
	MAS: mas,
	MSR: msr,
	NCR: ncr,
	NKS: nks,
	NOZ: noz,
	OAE: oae,
	PAC: pac,
	PDT: pdt,
	POE: poe,
	QFA: qfa,
	QTR: qtr,
	QXE: qxe,
	RAM: ram,
	ROU: rou,
	RPA: rpa,
	RYR: ryr,
	SAS: sas,
	SCX: scx,
	SIA: sia,
	SIL: sil,
	SKW: skw,
	SLI: sli,
	SVA: sva,
	SWA: swa,
	SWR: swr,
	TAM: tam,
	TAP: tap,
	THA: tha,
	THY: thy,
	TSC: tsc,
	UAE: uae,
	UAL: ual,
	UCA: uca,
	UPS: ups,
	VIR: vir,
	VIV: viv,
	VLG: vlg,
	VOI: voi,
	VOZ: voz,
	WGN: wgn,
	WJA: wja,
	WZZ: wzz,
};

export function airlineLogoSrc(code: string | null): string | null {
	if (!code) return null;
	return AIRLINE_LOGOS[code] ?? null;
}
