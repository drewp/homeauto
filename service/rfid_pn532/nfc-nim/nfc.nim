## -
##  Free/Libre Near Field Communication (NFC) library
##
##  Libnfc historical contributors:
##  Copyright (C) 2009      Roel Verdult
##  Copyright (C) 2009-2013 Romuald Conty
##  Copyright (C) 2010-2012 Romain Tartière
##  Copyright (C) 2010-2013 Philippe Teuwen
##  Copyright (C) 2012-2013 Ludovic Rousseau
##  See AUTHORS file for a more comprehensive list of contributors.
##  Additional contributors of this file:
##
##  This program is free software: you can redistribute it and/or modify it
##  under the terms of the GNU Lesser General Public License as published by the
##  Free Software Foundation, either version 3 of the License, or (at your
##  option) any later version.
##
##  This program is distributed in the hope that it will be useful, but WITHOUT
##  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
##  FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
##  more details.
##
##  You should have received a copy of the GNU Lesser General Public License
##  along with this program.  If not, see <http://www.gnu.org/licenses/>
##

const
  nfcLib* = "libnfc.so.5.0.1"

{.deadCodeElim: on.}
## *
##  @file nfc.h
##  @brief libnfc interface
##
##  Provide all usefull functions (API) to handle NFC devices.
##

## -
##  Free/Libre Near Field Communication (NFC) library
##
##  Libnfc historical contributors:
##  Copyright (C) 2009      Roel Verdult
##  Copyright (C) 2009-2013 Romuald Conty
##  Copyright (C) 2010-2012 Romain Tartière
##  Copyright (C) 2010-2013 Philippe Teuwen
##  Copyright (C) 2012-2013 Ludovic Rousseau
##  See AUTHORS file for a more comprehensive list of contributors.
##  Additional contributors of this file:
##
##  This program is free software: you can redistribute it and/or modify it
##  under the terms of the GNU Lesser General Public License as published by the
##  Free Software Foundation, either version 3 of the License, or (at your
##  option) any later version.
##
##  This program is distributed in the hope that it will be useful, but WITHOUT
##  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
##  FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
##  more details.
##
##  You should have received a copy of the GNU Lesser General Public License
##  along with this program.  If not, see <http://www.gnu.org/licenses/>
##
## *
##  @file nfc-types.h
##  @brief Define NFC types
##

const
  NFC_BUFSIZE_CONNSTRING* = 1024

## *
##  NFC context
##

type
  context* {.bycopy.} = object


## *
##  NFC device
##

type
  device* {.bycopy.} = object


## *
##  NFC device driver
##

type
  driver* {.bycopy.} = object


## *
##  Connection string
##

type
  connstring* = array[NFC_BUFSIZE_CONNSTRING, char]

## *
##  Properties
##

type ## *
    ##  Default command processing timeout
    ##  Property value's (duration) unit is ms and 0 means no timeout (infinite).
    ##  Default value is set by driver layer
    ##
  property* {.size: sizeof(cint).} = enum
    NP_TIMEOUT_COMMAND, ## *
                       ##  Timeout between ATR_REQ and ATR_RES
                       ##  When the device is in initiator mode, a target is considered as mute if no
                       ##  valid ATR_RES is received within this timeout value.
                       ##  Default value for this property is 103 ms on PN53x based devices.
                       ##
    NP_TIMEOUT_ATR, ## *
                   ##  Timeout value to give up reception from the target in case of no answer.
                   ##  Default value for this property is 52 ms).
                   ##
    NP_TIMEOUT_COM, ## * Let the PN53X chip handle the CRC bytes. This means that the chip appends
                   ##  the CRC bytes to the frames that are transmitted. It will parse the last
                   ##  bytes from received frames as incoming CRC bytes. They will be verified
                   ##  against the used modulation and protocol. If an frame is expected with
                   ##  incorrect CRC bytes this option should be disabled. Example frames where
                   ##  this is useful are the ATQA and UID+BCC that are transmitted without CRC
                   ##  bytes during the anti-collision phase of the ISO14443-A protocol.
    NP_HANDLE_CRC, ## * Parity bits in the network layer of ISO14443-A are by default generated and
                  ##  validated in the PN53X chip. This is a very convenient feature. On certain
                  ##  times though it is useful to get full control of the transmitted data. The
                  ##  proprietary MIFARE Classic protocol uses for example custom (encrypted)
                  ##  parity bits. For interoperability it is required to be completely
                  ##  compatible, including the arbitrary parity bits. When this option is
                  ##  disabled, the functions to communicating bits should be used.
    NP_HANDLE_PARITY, ## * This option can be used to enable or disable the electronic field of the
                     ##  NFC device.
    NP_ACTIVATE_FIELD, ## * The internal CRYPTO1 co-processor can be used to transmit messages
                      ##  encrypted. This option is automatically activated after a successful MIFARE
                      ##  Classic authentication.
    NP_ACTIVATE_CRYPTO1, ## * The default configuration defines that the PN53X chip will try indefinitely
                        ##  to invite a tag in the field to respond. This could be desired when it is
                        ##  certain a tag will enter the field. On the other hand, when this is
                        ##  uncertain, it will block the application. This option could best be compared
                        ##  to the (NON)BLOCKING option used by (socket)network programming.
    NP_INFINITE_SELECT, ## * If this option is enabled, frames that carry less than 4 bits are allowed.
                       ##  According to the standards these frames should normally be handles as
                       ##  invalid frames.
    NP_ACCEPT_INVALID_FRAMES, ## * If the NFC device should only listen to frames, it could be useful to let
                             ##  it gather multiple frames in a sequence. They will be stored in the internal
                             ##  FIFO of the PN53X chip. This could be retrieved by using the receive data
                             ##  functions. Note that if the chip runs out of bytes (FIFO = 64 bytes long),
                             ##  it will overwrite the first received frames, so quick retrieving of the
                             ##  received data is desirable.
    NP_ACCEPT_MULTIPLE_FRAMES, ## * This option can be used to enable or disable the auto-switching mode to
                              ##  ISO14443-4 is device is compliant.
                              ##  In initiator mode, it means that NFC chip will send RATS automatically when
                              ##  select and it will automatically poll for ISO14443-4 card when ISO14443A is
                              ##  requested.
                              ##  In target mode, with a NFC chip compliant (ie. PN532), the chip will
                              ##  emulate a 14443-4 PICC using hardware capability
    NP_AUTO_ISO14443_4,       ## * Use automatic frames encapsulation and chaining.
    NP_EASY_FRAMING,          ## * Force the chip to switch in ISO14443-A
    NP_FORCE_ISO14443_A,      ## * Force the chip to switch in ISO14443-B
    NP_FORCE_ISO14443_B,      ## * Force the chip to run at 106 kbps
    NP_FORCE_SPEED_106


##  Compiler directive, set struct alignment to 1 uint8_t for compatibility

## *
##  @enum nfc_dep_mode
##  @brief NFC D.E.P. (Data Exchange Protocol) active/passive mode
##

type
  dep_mode* {.size: sizeof(cint).} = enum
    NDM_UNDEFINED = 0, NDM_PASSIVE, NDM_ACTIVE


## *
##  @struct nfc_dep_info
##  @brief NFC target information in D.E.P. (Data Exchange Protocol) see ISO/IEC 18092 (NFCIP-1)
##

type
  dep_info* {.bycopy.} = object
    abtNFCID3*: array[10, uint8] ## * NFCID3
    ## * DID
    btDID*: uint8              ## * Supported send-bit rate
    btBS*: uint8               ## * Supported receive-bit rate
    btBR*: uint8               ## * Timeout value
    btTO*: uint8               ## * PP Parameters
    btPP*: uint8               ## * General Bytes
    abtGB*: array[48, uint8]
    szGB*: csize               ## * DEP mode
    ndm*: dep_mode


## *
##  @struct nfc_iso14443a_info
##  @brief NFC ISO14443A tag (MIFARE) information
##

type
  iso14443a_info* {.bycopy.} = object
    abtAtqa*: array[2, uint8]
    btSak*: uint8
    szUidLen*: csize
    abtUid*: array[10, uint8]
    szAtsLen*: csize
    abtAts*: array[254, uint8]  ##  Maximal theoretical ATS is FSD-2, FSD=256 for FSDI=8 in RATS


## *
##  @struct nfc_felica_info
##  @brief NFC FeLiCa tag information
##

type
  felica_info* {.bycopy.} = object
    szLen*: csize
    btResCode*: uint8
    abtId*: array[8, uint8]
    abtPad*: array[8, uint8]
    abtSysCode*: array[2, uint8]


## *
##  @struct nfc_iso14443b_info
##  @brief NFC ISO14443B tag information
##

type
  iso14443b_info* {.bycopy.} = object
    abtPupi*: array[4, uint8]   ## * abtPupi store PUPI contained in ATQB (Answer To reQuest of type B) (see ISO14443-3)
    ## * abtApplicationData store Application Data contained in ATQB (see ISO14443-3)
    abtApplicationData*: array[4, uint8] ## * abtProtocolInfo store Protocol Info contained in ATQB (see ISO14443-3)
    abtProtocolInfo*: array[3, uint8] ## * ui8CardIdentifier store CID (Card Identifier) attributted by PCD to the PICC
    ui8CardIdentifier*: uint8


## *
##  @struct nfc_iso14443bi_info
##  @brief NFC ISO14443B' tag information
##

type
  iso14443bi_info* {.bycopy.} = object
    abtDIV*: array[4, uint8]    ## * DIV: 4 LSBytes of tag serial number
    ## * Software version & type of REPGEN
    btVerLog*: uint8           ## * Config Byte, present if long REPGEN
    btConfig*: uint8           ## * ATR, if any
    szAtrLen*: csize
    abtAtr*: array[33, uint8]


## *
##  @struct nfc_iso14443b2sr_info
##  @brief NFC ISO14443-2B ST SRx tag information
##

type
  iso14443b2sr_info* {.bycopy.} = object
    abtUID*: array[8, uint8]


## *
##  @struct nfc_iso14443b2ct_info
##  @brief NFC ISO14443-2B ASK CTx tag information
##

type
  iso14443b2ct_info* {.bycopy.} = object
    abtUID*: array[4, uint8]
    btProdCode*: uint8
    btFabCode*: uint8


## *
##  @struct nfc_jewel_info
##  @brief NFC Jewel tag information
##

type
  jewel_info* {.bycopy.} = object
    btSensRes*: array[2, uint8]
    btId*: array[4, uint8]


## *
##  @union nfc_target_info
##  @brief Union between all kind of tags information structures.
##

type
  target_info* {.bycopy.} = object {.union.}
    nai*: iso14443a_info
    nfi*: felica_info
    nbi*: iso14443b_info
    nii*: iso14443bi_info
    nsi*: iso14443b2sr_info
    nci*: iso14443b2ct_info
    nji*: jewel_info
    ndi*: dep_info


## *
##  @enum nfc_baud_rate
##  @brief NFC baud rate enumeration
##

type
  baud_rate* {.size: sizeof(cint).} = enum
    NBR_UNDEFINED = 0, NBR_106, NBR_212, NBR_424, NBR_847


## *
##  @enum nfc_modulation_type
##  @brief NFC modulation type enumeration
##

type
  modulation_type* {.size: sizeof(cint).} = enum
    NMT_ISO14443A = 1, NMT_JEWEL, NMT_ISO14443B, NMT_ISO14443BI, ##  pre-ISO14443B aka ISO/IEC 14443 B' or Type B'
    NMT_ISO14443B2SR,         ##  ISO14443-2B ST SRx
    NMT_ISO14443B2CT,         ##  ISO14443-2B ASK CTx
    NMT_FELICA, NMT_DEP


## *
##  @enum nfc_mode
##  @brief NFC mode type enumeration
##

type
  mode* {.size: sizeof(cint).} = enum
    N_TARGET, N_INITIATOR


## *
##  @struct nfc_modulation
##  @brief NFC modulation structure
##

type
  modulation* {.bycopy.} = object
    nmt*: modulation_type
    nbr*: baud_rate


## *
##  @struct nfc_target
##  @brief NFC target structure
##

type
  target* {.bycopy.} = object
    nti*: target_info
    nm*: modulation


##  Reset struct alignment to default

##  Library initialization/deinitialization

proc init*(context: ptr ptr context) {.cdecl, importc: "nfc_init", dynlib: nfcLib.}
proc exit*(context: ptr context) {.cdecl, importc: "nfc_exit", dynlib: nfcLib.}
proc register_driver*(driver: ptr driver): cint {.cdecl,
    importc: "nfc_register_driver", dynlib: nfcLib.}
##  NFC Device/Hardware manipulation

proc open*(context: ptr context; connstring: connstring): ptr device {.cdecl,
    importc: "nfc_open", dynlib: nfcLib.}
proc close*(pnd: ptr device) {.cdecl, importc: "nfc_close", dynlib: nfcLib.}
proc abort_command*(pnd: ptr device): cint {.cdecl, importc: "nfc_abort_command",
                                        dynlib: nfcLib.}
proc list_devices*(context: ptr context; connstrings: ptr connstring;
                  connstrings_len: csize): csize {.cdecl,
    importc: "nfc_list_devices", dynlib: nfcLib.}
proc idle*(pnd: ptr device): cint {.cdecl, importc: "nfc_idle", dynlib: nfcLib.}
##  NFC initiator: act as "reader"

proc initiator_init*(pnd: ptr device): cint {.cdecl, importc: "nfc_initiator_init",
    dynlib: nfcLib.}
proc initiator_init_secure_element*(pnd: ptr device): cint {.cdecl,
    importc: "nfc_initiator_init_secure_element", dynlib: nfcLib.}
proc initiator_select_passive_target*(pnd: ptr device; nm: modulation;
                                     pbtInitData: ptr uint8; szInitData: csize;
                                     pnt: ptr target): cint {.cdecl,
    importc: "nfc_initiator_select_passive_target", dynlib: nfcLib.}
proc initiator_list_passive_targets*(pnd: ptr device; nm: modulation; ant: ptr target;
                                    szTargets: csize): cint {.cdecl,
    importc: "nfc_initiator_list_passive_targets", dynlib: nfcLib.}
proc initiator_poll_target*(pnd: ptr device; pnmTargetTypes: ptr modulation;
                           szTargetTypes: csize; uiPollNr: uint8; uiPeriod: uint8;
                           pnt: ptr target): cint {.cdecl,
    importc: "nfc_initiator_poll_target", dynlib: nfcLib.}
proc initiator_select_dep_target*(pnd: ptr device; ndm: dep_mode; nbr: baud_rate;
                                 pndiInitiator: ptr dep_info; pnt: ptr target;
                                 timeout: cint): cint {.cdecl,
    importc: "nfc_initiator_select_dep_target", dynlib: nfcLib.}
proc initiator_poll_dep_target*(pnd: ptr device; ndm: dep_mode; nbr: baud_rate;
                               pndiInitiator: ptr dep_info; pnt: ptr target;
                               timeout: cint): cint {.cdecl,
    importc: "nfc_initiator_poll_dep_target", dynlib: nfcLib.}
proc initiator_deselect_target*(pnd: ptr device): cint {.cdecl,
    importc: "nfc_initiator_deselect_target", dynlib: nfcLib.}
proc initiator_transceive_bytes*(pnd: ptr device; pbtTx: ptr uint8; szTx: csize;
                                pbtRx: ptr uint8; szRx: csize; timeout: cint): cint {.
    cdecl, importc: "nfc_initiator_transceive_bytes", dynlib: nfcLib.}
proc initiator_transceive_bits*(pnd: ptr device; pbtTx: ptr uint8; szTxBits: csize;
                               pbtTxPar: ptr uint8; pbtRx: ptr uint8; szRx: csize;
                               pbtRxPar: ptr uint8): cint {.cdecl,
    importc: "nfc_initiator_transceive_bits", dynlib: nfcLib.}
proc initiator_transceive_bytes_timed*(pnd: ptr device; pbtTx: ptr uint8; szTx: csize;
                                      pbtRx: ptr uint8; szRx: csize;
                                      cycles: ptr uint32): cint {.cdecl,
    importc: "nfc_initiator_transceive_bytes_timed", dynlib: nfcLib.}
proc initiator_transceive_bits_timed*(pnd: ptr device; pbtTx: ptr uint8;
                                     szTxBits: csize; pbtTxPar: ptr uint8;
                                     pbtRx: ptr uint8; szRx: csize;
                                     pbtRxPar: ptr uint8; cycles: ptr uint32): cint {.
    cdecl, importc: "nfc_initiator_transceive_bits_timed", dynlib: nfcLib.}
proc initiator_target_is_present*(pnd: ptr device; pnt: ptr target): cint {.cdecl,
    importc: "nfc_initiator_target_is_present", dynlib: nfcLib.}
##  NFC target: act as tag (i.e. MIFARE Classic) or NFC target device.

proc target_init*(pnd: ptr device; pnt: ptr target; pbtRx: ptr uint8; szRx: csize;
                 timeout: cint): cint {.cdecl, importc: "nfc_target_init",
                                     dynlib: nfcLib.}
proc target_send_bytes*(pnd: ptr device; pbtTx: ptr uint8; szTx: csize; timeout: cint): cint {.
    cdecl, importc: "nfc_target_send_bytes", dynlib: nfcLib.}
proc target_receive_bytes*(pnd: ptr device; pbtRx: ptr uint8; szRx: csize; timeout: cint): cint {.
    cdecl, importc: "nfc_target_receive_bytes", dynlib: nfcLib.}
proc target_send_bits*(pnd: ptr device; pbtTx: ptr uint8; szTxBits: csize;
                      pbtTxPar: ptr uint8): cint {.cdecl,
    importc: "nfc_target_send_bits", dynlib: nfcLib.}
proc target_receive_bits*(pnd: ptr device; pbtRx: ptr uint8; szRx: csize;
                         pbtRxPar: ptr uint8): cint {.cdecl,
    importc: "nfc_target_receive_bits", dynlib: nfcLib.}
##  Error reporting

proc strerror*(pnd: ptr device): cstring {.cdecl, importc: "nfc_strerror",
                                      dynlib: nfcLib.}
proc strerror_r*(pnd: ptr device; buf: cstring; buflen: csize): cint {.cdecl,
    importc: "nfc_strerror_r", dynlib: nfcLib.}
proc perror*(pnd: ptr device; s: cstring) {.cdecl, importc: "nfc_perror", dynlib: nfcLib.}
proc device_get_last_error*(pnd: ptr device): cint {.cdecl,
    importc: "nfc_device_get_last_error", dynlib: nfcLib.}
##  Special data accessors

proc device_get_name*(pnd: ptr device): cstring {.cdecl,
    importc: "nfc_device_get_name", dynlib: nfcLib.}
proc device_get_connstring*(pnd: ptr device): cstring {.cdecl,
    importc: "nfc_device_get_connstring", dynlib: nfcLib.}
proc device_get_supported_modulation*(pnd: ptr device; mode: mode;
                                     supported_mt: ptr ptr modulation_type): cint {.
    cdecl, importc: "nfc_device_get_supported_modulation", dynlib: nfcLib.}
proc device_get_supported_baud_rate*(pnd: ptr device; nmt: modulation_type;
                                    supported_br: ptr ptr baud_rate): cint {.cdecl,
    importc: "nfc_device_get_supported_baud_rate", dynlib: nfcLib.}
##  Properties accessors

proc device_set_property_int*(pnd: ptr device; property: property; value: cint): cint {.
    cdecl, importc: "nfc_device_set_property_int", dynlib: nfcLib.}
proc device_set_property_bool*(pnd: ptr device; property: property; bEnable: bool): cint {.
    cdecl, importc: "nfc_device_set_property_bool", dynlib: nfcLib.}
##  Misc. functions

proc iso14443a_crc*(pbtData: ptr uint8; szLen: csize; pbtCrc: ptr uint8) {.cdecl,
    importc: "iso14443a_crc", dynlib: nfcLib.}
proc iso14443a_crc_append*(pbtData: ptr uint8; szLen: csize) {.cdecl,
    importc: "iso14443a_crc_append", dynlib: nfcLib.}
proc iso14443b_crc*(pbtData: ptr uint8; szLen: csize; pbtCrc: ptr uint8) {.cdecl,
    importc: "iso14443b_crc", dynlib: nfcLib.}
proc iso14443b_crc_append*(pbtData: ptr uint8; szLen: csize) {.cdecl,
    importc: "iso14443b_crc_append", dynlib: nfcLib.}
proc iso14443a_locate_historical_bytes*(pbtAts: ptr uint8; szAts: csize;
                                       pszTk: ptr csize): ptr uint8 {.cdecl,
    importc: "iso14443a_locate_historical_bytes", dynlib: nfcLib.}
proc free*(p: pointer) {.cdecl, importc: "nfc_free", dynlib: nfcLib.}
proc version*(): cstring {.cdecl, importc: "nfc_version", dynlib: nfcLib.}
proc device_get_information_about*(pnd: ptr device; buf: cstringArray): cint {.cdecl,
    importc: "nfc_device_get_information_about", dynlib: nfcLib.}
##  String converter functions

proc str_nfc_modulation_type*(nmt: modulation_type): cstring {.cdecl,
    importc: "str_nfc_modulation_type", dynlib: nfcLib.}
proc str_nfc_baud_rate*(nbr: baud_rate): cstring {.cdecl,
    importc: "str_nfc_baud_rate", dynlib: nfcLib.}
proc str_nfc_target*(buf: cstringArray; pnt: ptr target; verbose: bool): cint {.cdecl,
    importc: "str_nfc_target", dynlib: nfcLib.}
##  Error codes
## * @ingroup error
##  @hideinitializer
##  Success (no error)
##

const
  NFC_SUCCESS* = 0

## * @ingroup error
##  @hideinitializer
##  Input / output error, device may not be usable anymore without re-open it
##

const
  NFC_EIO* = -1

## * @ingroup error
##  @hideinitializer
##  Invalid argument(s)
##

const
  NFC_EINVARG* = -2

## * @ingroup error
##  @hideinitializer
##   Operation not supported by device
##

const
  NFC_EDEVNOTSUPP* = -3

## * @ingroup error
##  @hideinitializer
##  No such device
##

const
  NFC_ENOTSUCHDEV* = -4

## * @ingroup error
##  @hideinitializer
##  Buffer overflow
##

const
  NFC_EOVFLOW* = -5

## * @ingroup error
##  @hideinitializer
##  Operation timed out
##

const
  NFC_ETIMEOUT* = -6

## * @ingroup error
##  @hideinitializer
##  Operation aborted (by user)
##

const
  NFC_EOPABORTED* = -7

## * @ingroup error
##  @hideinitializer
##  Not (yet) implemented
##

const
  NFC_ENOTIMPL* = -8

## * @ingroup error
##  @hideinitializer
##  Target released
##

const
  NFC_ETGRELEASED* = -10

## * @ingroup error
##  @hideinitializer
##  Error while RF transmission
##

const
  NFC_ERFTRANS* = -20

## * @ingroup error
##  @hideinitializer
##  MIFARE Classic: authentication failed
##

const
  NFC_EMFCAUTHFAIL* = -30

## * @ingroup error
##  @hideinitializer
##  Software error (allocation, file/pipe creation, etc.)
##

const
  NFC_ESOFT* = -80

## * @ingroup error
##  @hideinitializer
##  Device's internal chip error
##

const
  NFC_ECHIP* = -90
