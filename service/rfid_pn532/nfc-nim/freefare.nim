const
  freefareLib* = "libfreefare.so.0.0.0"
  nfcHeader* = "nfc/nfc.h"
  freefareHeader* = "freefare.h"

{.deadCodeElim: on.}
import nfc
type
  freefare_tag_type* {.size: sizeof(cint).} = enum
    FELICA, MIFARE_MINI, MIFARE_CLASSIC_1K, MIFARE_CLASSIC_4K, MIFARE_DESFIRE, ##
                                                                          ## MIFARE_PLUS_S2K,
                                                                          ##
                                                                          ## MIFARE_PLUS_S4K,
                                                                          ##
                                                                          ## MIFARE_PLUS_X2K,
                                                                          ##
                                                                          ## MIFARE_PLUS_X4K,
    MIFARE_ULTRALIGHT, MIFARE_ULTRALIGHT_C, NTAG_21x


type
  freefare_tag* {.importc: "struct freefare_tag", header: freefareHeader, bycopy.} = object

  FreefareTag* = ptr freefare_tag

##  Replace any MifareTag by the generic FreefareTag.

type
  MifareTag* = ptr freefare_tag
  mifare_desfire_key* {.importc: "struct mifare_desfire_key",
                       header: freefareHeader, bycopy.} = object

  MifareDESFireKey* = ptr mifare_desfire_key
  ntag21x_key* {.importc: "struct ntag21x_key", header: freefareHeader, bycopy.} = object

  NTAG21xKey* = ptr ntag21x_key
  MifareUltralightPageNumber* = uint8
  MifareUltralightPage* = array[4, cuchar]

proc freefare_get_tags*(device: ptr device): ptr FreefareTag {.cdecl,
    importc: "freefare_get_tags", dynlib: freefareLib.}
proc freefare_tag_new*(device: ptr device; target: target): FreefareTag {.cdecl,
    importc: "freefare_tag_new", dynlib: freefareLib.}
proc freefare_get_tag_type*(tag: FreefareTag): freefare_tag_type {.cdecl,
    importc: "freefare_get_tag_type", dynlib: freefareLib.}
proc freefare_get_tag_friendly_name*(tag: FreefareTag): cstring {.cdecl,
    importc: "freefare_get_tag_friendly_name", dynlib: freefareLib.}
proc freefare_get_tag_uid*(tag: FreefareTag): cstring {.cdecl,
    importc: "freefare_get_tag_uid", dynlib: freefareLib.}
proc freefare_free_tag*(tag: FreefareTag) {.cdecl, importc: "freefare_free_tag",
    dynlib: freefareLib.}
proc freefare_free_tags*(tags: ptr FreefareTag) {.cdecl,
    importc: "freefare_free_tags", dynlib: freefareLib.}
proc freefare_selected_tag_is_present*(device: ptr device): bool {.cdecl,
    importc: "freefare_selected_tag_is_present", dynlib: freefareLib.}
proc freefare_strerror*(tag: FreefareTag): cstring {.cdecl,
    importc: "freefare_strerror", dynlib: freefareLib.}
proc freefare_strerror_r*(tag: FreefareTag; buffer: cstring; len: csize): cint {.cdecl,
    importc: "freefare_strerror_r", dynlib: freefareLib.}
proc freefare_perror*(tag: FreefareTag; string: cstring) {.cdecl,
    importc: "freefare_perror", dynlib: freefareLib.}
proc felica_taste*(device: ptr device; target: target): bool {.cdecl,
    importc: "felica_taste", dynlib: freefareLib.}
const
  FELICA_SC_RW* = 0x00000009
  FELICA_SC_RO* = 0x0000000B

proc felica_tag_new*(device: ptr device; target: target): FreefareTag {.cdecl,
    importc: "felica_tag_new", dynlib: freefareLib.}
proc felica_tag_free*(tag: FreefareTag) {.cdecl, importc: "felica_tag_free",
                                       dynlib: freefareLib.}
proc felica_read*(tag: FreefareTag; service: uint16; `block`: uint8; data: ptr uint8;
                 length: csize): int32 {.cdecl, importc: "felica_read",
                                      dynlib: freefareLib.}
proc felica_read_ex*(tag: FreefareTag; service: uint16; block_count: uint8;
                    blocks: ptr uint8; data: ptr uint8; length: csize): int32 {.cdecl,
    importc: "felica_read_ex", dynlib: freefareLib.}
proc felica_write*(tag: FreefareTag; service: uint16; `block`: uint8; data: ptr uint8;
                  length: csize): int32 {.cdecl, importc: "felica_write",
                                       dynlib: freefareLib.}
proc felica_write_ex*(tag: FreefareTag; service: uint16; block_count: uint8;
                     blocks: ptr uint8; data: ptr uint8; length: csize): int32 {.cdecl,
    importc: "felica_write_ex", dynlib: freefareLib.}
proc mifare_ultralight_taste*(device: ptr device; target: target): bool {.cdecl,
    importc: "mifare_ultralight_taste", dynlib: freefareLib.}
proc mifare_ultralightc_taste*(device: ptr device; target: target): bool {.cdecl,
    importc: "mifare_ultralightc_taste", dynlib: freefareLib.}
proc mifare_ultralight_tag_new*(device: ptr device; target: target): FreefareTag {.
    cdecl, importc: "mifare_ultralight_tag_new", dynlib: freefareLib.}
proc mifare_ultralightc_tag_new*(device: ptr device; target: target): FreefareTag {.
    cdecl, importc: "mifare_ultralightc_tag_new", dynlib: freefareLib.}
proc mifare_ultralight_tag_free*(tag: FreefareTag) {.cdecl,
    importc: "mifare_ultralight_tag_free", dynlib: freefareLib.}
proc mifare_ultralightc_tag_free*(tag: FreefareTag) {.cdecl,
    importc: "mifare_ultralightc_tag_free", dynlib: freefareLib.}
proc mifare_ultralight_connect*(tag: FreefareTag): cint {.cdecl,
    importc: "mifare_ultralight_connect", dynlib: freefareLib.}
proc mifare_ultralight_disconnect*(tag: FreefareTag): cint {.cdecl,
    importc: "mifare_ultralight_disconnect", dynlib: freefareLib.}
proc mifare_ultralight_read*(tag: FreefareTag; page: MifareUltralightPageNumber;
                            data: ptr MifareUltralightPage): cint {.cdecl,
    importc: "mifare_ultralight_read", dynlib: freefareLib.}
proc mifare_ultralight_write*(tag: FreefareTag; page: MifareUltralightPageNumber;
                             data: MifareUltralightPage): cint {.cdecl,
    importc: "mifare_ultralight_write", dynlib: freefareLib.}
proc mifare_ultralightc_authenticate*(tag: FreefareTag; key: MifareDESFireKey): cint {.
    cdecl, importc: "mifare_ultralightc_authenticate", dynlib: freefareLib.}
proc mifare_ultralightc_set_key*(tag: FreefareTag; key: MifareDESFireKey): cint {.
    cdecl, importc: "mifare_ultralightc_set_key", dynlib: freefareLib.}
proc is_mifare_ultralight*(tag: FreefareTag): bool {.cdecl,
    importc: "is_mifare_ultralight", dynlib: freefareLib.}
proc is_mifare_ultralightc*(tag: FreefareTag): bool {.cdecl,
    importc: "is_mifare_ultralightc", dynlib: freefareLib.}
proc is_mifare_ultralightc_on_reader*(device: ptr device; nai: iso14443a_info): bool {.
    cdecl, importc: "is_mifare_ultralightc_on_reader", dynlib: freefareLib.}
proc ntag21x_taste*(device: ptr device; target: target): bool {.cdecl,
    importc: "ntag21x_taste", dynlib: freefareLib.}
proc ntag21x_last_error*(tag: FreefareTag): uint8 {.cdecl,
    importc: "ntag21x_last_error", dynlib: freefareLib.}
##  NTAG21x access features

const
  NTAG_PROT* = 0x00000080
  NTAG_CFGLCK* = 0x00000040
  NTAG_NFC_CNT_EN* = 0x00000020
  NTAG_NFC_CNT_PWD_PROT* = 0x00000010
  NTAG_AUTHLIM* = 0x00000007

type
  ntag_tag_subtype* {.size: sizeof(cint).} = enum
    NTAG_UNKNOWN, NTAG_213, NTAG_215, NTAG_216


proc ntag21x_tag_new*(device: ptr device; target: target): FreefareTag {.cdecl,
    importc: "ntag21x_tag_new", dynlib: freefareLib.}
proc ntag21x_tag_reuse*(tag: FreefareTag): FreefareTag {.cdecl,
    importc: "ntag21x_tag_reuse", dynlib: freefareLib.}
##  Copy data from Ultralight tag to new NTAG21x, don't forget to free your old tag

proc ntag21x_key_new*(data: array[4, uint8]; pack: array[2, uint8]): NTAG21xKey {.cdecl,
    importc: "ntag21x_key_new", dynlib: freefareLib.}
##  Create new key

proc ntag21x_key_free*(key: NTAG21xKey) {.cdecl, importc: "ntag21x_key_free",
                                       dynlib: freefareLib.}
##  Clear key from memory

proc ntag21x_tag_free*(tag: FreefareTag) {.cdecl, importc: "ntag21x_tag_free",
                                        dynlib: freefareLib.}
proc ntag21x_connect*(tag: FreefareTag): cint {.cdecl, importc: "ntag21x_connect",
    dynlib: freefareLib.}
proc ntag21x_disconnect*(tag: FreefareTag): cint {.cdecl,
    importc: "ntag21x_disconnect", dynlib: freefareLib.}
proc ntag21x_get_info*(tag: FreefareTag): cint {.cdecl, importc: "ntag21x_get_info",
    dynlib: freefareLib.}
##  Get all information about tag (size,vendor ...)

proc ntag21x_get_subtype*(tag: FreefareTag): ntag_tag_subtype {.cdecl,
    importc: "ntag21x_get_subtype", dynlib: freefareLib.}
##  Get subtype of tag

proc ntag21x_get_last_page*(tag: FreefareTag): uint8 {.cdecl,
    importc: "ntag21x_get_last_page", dynlib: freefareLib.}
##  Get last page address based on gathered info from function above

proc ntag21x_read_signature*(tag: FreefareTag; data: ptr uint8): cint {.cdecl,
    importc: "ntag21x_read_signature", dynlib: freefareLib.}
##  Get tag signature

proc ntag21x_set_pwd*(tag: FreefareTag; data: array[4, uint8]): cint {.cdecl,
    importc: "ntag21x_set_pwd", dynlib: freefareLib.}
##  Set password

proc ntag21x_set_pack*(tag: FreefareTag; data: array[2, uint8]): cint {.cdecl,
    importc: "ntag21x_set_pack", dynlib: freefareLib.}
##  Set pack

proc ntag21x_set_key*(tag: FreefareTag; key: NTAG21xKey): cint {.cdecl,
    importc: "ntag21x_set_key", dynlib: freefareLib.}
##  Set key

proc ntag21x_set_auth*(tag: FreefareTag; byte: uint8): cint {.cdecl,
    importc: "ntag21x_set_auth", dynlib: freefareLib.}
##  Set AUTH0 byte (from which page starts password protection)

proc ntag21x_get_auth*(tag: FreefareTag; byte: ptr uint8): cint {.cdecl,
    importc: "ntag21x_get_auth", dynlib: freefareLib.}
##  Get AUTH0 byte

proc ntag21x_access_enable*(tag: FreefareTag; byte: uint8): cint {.cdecl,
    importc: "ntag21x_access_enable", dynlib: freefareLib.}
##  Enable access feature in ACCESS byte

proc ntag21x_access_disable*(tag: FreefareTag; byte: uint8): cint {.cdecl,
    importc: "ntag21x_access_disable", dynlib: freefareLib.}
##  Disable access feature in ACCESS byte

proc ntag21x_get_access*(tag: FreefareTag; byte: ptr uint8): cint {.cdecl,
    importc: "ntag21x_get_access", dynlib: freefareLib.}
##  Get ACCESS byte

proc ntag21x_check_access*(tag: FreefareTag; byte: uint8; result: ptr bool): cint {.
    cdecl, importc: "ntag21x_check_access", dynlib: freefareLib.}
##  Check if access feature is enabled

proc ntag21x_get_authentication_limit*(tag: FreefareTag; byte: ptr uint8): cint {.
    cdecl, importc: "ntag21x_get_authentication_limit", dynlib: freefareLib.}
##  Get authentication limit

proc ntag21x_set_authentication_limit*(tag: FreefareTag; byte: uint8): cint {.cdecl,
    importc: "ntag21x_set_authentication_limit", dynlib: freefareLib.}
##  Set authentication limit (0x00 = disabled, [0x01,0x07] = valid range, > 0x07 invalid range)

proc ntag21x_read*(tag: FreefareTag; page: uint8; data: ptr uint8): cint {.cdecl,
    importc: "ntag21x_read", dynlib: freefareLib.}
##  Read 16 bytes starting from page

proc ntag21x_read4*(tag: FreefareTag; page: uint8; data: ptr uint8): cint {.cdecl,
    importc: "ntag21x_read4", dynlib: freefareLib.}
##  Read 4 bytes on page

proc ntag21x_fast_read*(tag: FreefareTag; start_page: uint8; end_page: uint8;
                       data: ptr uint8): cint {.cdecl, importc: "ntag21x_fast_read",
    dynlib: freefareLib.}
##  Read n*4 bytes from range [start_page,end_page]

proc ntag21x_fast_read4*(tag: FreefareTag; page: uint8; data: ptr uint8): cint {.cdecl,
    importc: "ntag21x_fast_read4", dynlib: freefareLib.}
##  Fast read certain page

proc ntag21x_read_cnt*(tag: FreefareTag; data: ptr uint8): cint {.cdecl,
    importc: "ntag21x_read_cnt", dynlib: freefareLib.}
##  Read 3-byte NFC counter if enabled else it returns error

proc ntag21x_write*(tag: FreefareTag; page: uint8; data: array[4, uint8]): cint {.cdecl,
    importc: "ntag21x_write", dynlib: freefareLib.}
##  Write 4 bytes to page

proc ntag21x_compatibility_write*(tag: FreefareTag; page: uint8;
                                 data: array[4, uint8]): cint {.cdecl,
    importc: "ntag21x_compatibility_write", dynlib: freefareLib.}
##  Writes 4 bytes to page with mifare classic write

proc ntag21x_authenticate*(tag: FreefareTag; key: NTAG21xKey): cint {.cdecl,
    importc: "ntag21x_authenticate", dynlib: freefareLib.}
##  Authenticate with tag

proc is_ntag21x*(tag: FreefareTag): bool {.cdecl, importc: "is_ntag21x",
                                       dynlib: freefareLib.}
##  Check if tag type is NTAG21x

proc ntag21x_is_auth_supported*(device: ptr device; nai: iso14443a_info): bool {.cdecl,
    importc: "ntag21x_is_auth_supported", dynlib: freefareLib.}
##  Check if tag supports 21x commands

proc mifare_mini_taste*(device: ptr device; target: target): bool {.cdecl,
    importc: "mifare_mini_taste", dynlib: freefareLib.}
proc mifare_classic1k_taste*(device: ptr device; target: target): bool {.cdecl,
    importc: "mifare_classic1k_taste", dynlib: freefareLib.}
proc mifare_classic4k_taste*(device: ptr device; target: target): bool {.cdecl,
    importc: "mifare_classic4k_taste", dynlib: freefareLib.}
proc mifare_mini_tag_new*(device: ptr device; target: target): FreefareTag {.cdecl,
    importc: "mifare_mini_tag_new", dynlib: freefareLib.}
proc mifare_classic1k_tag_new*(device: ptr device; target: target): FreefareTag {.
    cdecl, importc: "mifare_classic1k_tag_new", dynlib: freefareLib.}
proc mifare_classic4k_tag_new*(device: ptr device; target: target): FreefareTag {.
    cdecl, importc: "mifare_classic4k_tag_new", dynlib: freefareLib.}
proc mifare_classic_tag_free*(tag: FreefareTag) {.cdecl,
    importc: "mifare_classic_tag_free", dynlib: freefareLib.}
type
  MifareClassicBlock* = array[16, cuchar]
  MifareClassicSectorNumber* = uint8
  MifareClassicBlockNumber* = cuchar
  MifareClassicKeyType* {.size: sizeof(cint).} = enum
    MFC_KEY_A, MFC_KEY_B
  MifareClassicKey* = array[6, cuchar]


##  NFC Forum public key

var mifare_classic_nfcforum_public_key_a* {.
    importc: "mifare_classic_nfcforum_public_key_a", dynlib: freefareLib.}: MifareClassicKey

proc mifare_classic_connect*(tag: FreefareTag): cint {.cdecl,
    importc: "mifare_classic_connect", dynlib: freefareLib.}
proc mifare_classic_disconnect*(tag: FreefareTag): cint {.cdecl,
    importc: "mifare_classic_disconnect", dynlib: freefareLib.}
proc mifare_classic_authenticate*(tag: FreefareTag;
                                 `block`: MifareClassicBlockNumber;
                                 key: MifareClassicKey;
                                 key_type: MifareClassicKeyType): cint {.cdecl,
    importc: "mifare_classic_authenticate", dynlib: freefareLib.}
proc mifare_classic_read*(tag: FreefareTag; `block`: MifareClassicBlockNumber;
                         data: ptr MifareClassicBlock): cint {.cdecl,
    importc: "mifare_classic_read", dynlib: freefareLib.}
proc mifare_classic_init_value*(tag: FreefareTag;
                               `block`: MifareClassicBlockNumber; value: int32;
                               adr: MifareClassicBlockNumber): cint {.cdecl,
    importc: "mifare_classic_init_value", dynlib: freefareLib.}
proc mifare_classic_read_value*(tag: FreefareTag;
                               `block`: MifareClassicBlockNumber;
                               value: ptr int32; adr: ptr MifareClassicBlockNumber): cint {.
    cdecl, importc: "mifare_classic_read_value", dynlib: freefareLib.}
proc mifare_classic_write*(tag: FreefareTag; `block`: MifareClassicBlockNumber;
                          data: MifareClassicBlock): cint {.cdecl,
    importc: "mifare_classic_write", dynlib: freefareLib.}
proc mifare_classic_increment*(tag: FreefareTag; `block`: MifareClassicBlockNumber;
                              amount: uint32): cint {.cdecl,
    importc: "mifare_classic_increment", dynlib: freefareLib.}
proc mifare_classic_decrement*(tag: FreefareTag; `block`: MifareClassicBlockNumber;
                              amount: uint32): cint {.cdecl,
    importc: "mifare_classic_decrement", dynlib: freefareLib.}
proc mifare_classic_restore*(tag: FreefareTag; `block`: MifareClassicBlockNumber): cint {.
    cdecl, importc: "mifare_classic_restore", dynlib: freefareLib.}
proc mifare_classic_transfer*(tag: FreefareTag; `block`: MifareClassicBlockNumber): cint {.
    cdecl, importc: "mifare_classic_transfer", dynlib: freefareLib.}
proc mifare_classic_get_trailer_block_permission*(tag: FreefareTag;
    `block`: MifareClassicBlockNumber; permission: uint16;
    key_type: MifareClassicKeyType): cint {.cdecl,
    importc: "mifare_classic_get_trailer_block_permission", dynlib: freefareLib.}
proc mifare_classic_get_data_block_permission*(tag: FreefareTag;
    `block`: MifareClassicBlockNumber; permission: cuchar;
    key_type: MifareClassicKeyType): cint {.cdecl,
    importc: "mifare_classic_get_data_block_permission", dynlib: freefareLib.}
proc mifare_classic_format_sector*(tag: FreefareTag;
                                  sector: MifareClassicSectorNumber): cint {.cdecl,
    importc: "mifare_classic_format_sector", dynlib: freefareLib.}
proc mifare_classic_trailer_block*(`block`: ptr MifareClassicBlock;
                                  key_a: MifareClassicKey; ab_0: uint8; ab_1: uint8;
                                  ab_2: uint8; ab_tb: uint8; gpb: uint8;
                                  key_b: MifareClassicKey) {.cdecl,
    importc: "mifare_classic_trailer_block", dynlib: freefareLib.}
proc mifare_classic_block_sector*(`block`: MifareClassicBlockNumber): MifareClassicSectorNumber {.
    cdecl, importc: "mifare_classic_block_sector", dynlib: freefareLib.}
proc mifare_classic_sector_first_block*(sector: MifareClassicSectorNumber): MifareClassicBlockNumber {.
    cdecl, importc: "mifare_classic_sector_first_block", dynlib: freefareLib.}
proc mifare_classic_sector_block_count*(sector: MifareClassicSectorNumber): csize {.
    cdecl, importc: "mifare_classic_sector_block_count", dynlib: freefareLib.}
proc mifare_classic_sector_last_block*(sector: MifareClassicSectorNumber): MifareClassicBlockNumber {.
    cdecl, importc: "mifare_classic_sector_last_block", dynlib: freefareLib.}
const
  C_000* = 0
  C_001* = 1
  C_010* = 2
  C_011* = 3
  C_100* = 4
  C_101* = 5
  C_110* = 6
  C_111* = 7
  C_DEFAULT* = 255

##  MIFARE Classic Access Bits

const
  MCAB_R* = 0x00000008
  MCAB_W* = 0x00000004
  MCAB_D* = 0x00000002
  MCAB_I* = 0x00000001
  MCAB_READ_KEYA* = 0x00000400
  MCAB_WRITE_KEYA* = 0x00000100
  MCAB_READ_ACCESS_BITS* = 0x00000040
  MCAB_WRITE_ACCESS_BITS* = 0x00000010
  MCAB_READ_KEYB* = 0x00000004
  MCAB_WRITE_KEYB* = 0x00000001

type
  mad_aid* {.importc: "struct mad_aid", header: freefareHeader, bycopy.} = object
    application_code* {.importc: "application_code".}: uint8
    function_cluster_code* {.importc: "function_cluster_code".}: uint8

  MadAid* = mad_aid
  mad* {.importc: "struct mad", header: freefareHeader, bycopy.} = object

  Mad* = ptr mad

##  MAD Public read key A

var mad_public_key_a* {.importc: "mad_public_key_a", dynlib: freefareLib.}: MifareClassicKey

##  AID - Adminisration codes

var mad_free_aid* {.importc: "mad_free_aid", dynlib: freefareLib.}: MadAid

var mad_defect_aid* {.importc: "mad_defect_aid", dynlib: freefareLib.}: MadAid

var mad_reserved_aid* {.importc: "mad_reserved_aid", dynlib: freefareLib.}: MadAid

var mad_card_holder_aid* {.importc: "mad_card_holder_aid", dynlib: freefareLib.}: MadAid

var mad_not_applicable_aid* {.importc: "mad_not_applicable_aid", dynlib: freefareLib.}: MadAid

##  NFC Forum AID

var mad_nfcforum_aid* {.importc: "mad_nfcforum_aid", dynlib: freefareLib.}: MadAid

proc mad_new*(version: uint8): Mad {.cdecl, importc: "mad_new", dynlib: freefareLib.}
proc mad_read*(tag: FreefareTag): Mad {.cdecl, importc: "mad_read", dynlib: freefareLib.}
proc mad_write*(tag: FreefareTag; mad: Mad; key_b_sector_00: MifareClassicKey;
               key_b_sector_10: MifareClassicKey): cint {.cdecl,
    importc: "mad_write", dynlib: freefareLib.}
proc mad_get_version*(mad: Mad): cint {.cdecl, importc: "mad_get_version",
                                    dynlib: freefareLib.}
proc mad_set_version*(mad: Mad; version: uint8) {.cdecl, importc: "mad_set_version",
    dynlib: freefareLib.}
proc mad_get_card_publisher_sector*(mad: Mad): MifareClassicSectorNumber {.cdecl,
    importc: "mad_get_card_publisher_sector", dynlib: freefareLib.}
proc mad_set_card_publisher_sector*(mad: Mad; cps: MifareClassicSectorNumber): cint {.
    cdecl, importc: "mad_set_card_publisher_sector", dynlib: freefareLib.}
proc mad_get_aid*(mad: Mad; sector: MifareClassicSectorNumber; aid: ptr MadAid): cint {.
    cdecl, importc: "mad_get_aid", dynlib: freefareLib.}
proc mad_set_aid*(mad: Mad; sector: MifareClassicSectorNumber; aid: MadAid): cint {.
    cdecl, importc: "mad_set_aid", dynlib: freefareLib.}
proc mad_sector_reserved*(sector: MifareClassicSectorNumber): bool {.cdecl,
    importc: "mad_sector_reserved", dynlib: freefareLib.}
proc mad_free*(mad: Mad) {.cdecl, importc: "mad_free", dynlib: freefareLib.}
proc mifare_application_alloc*(mad: Mad; aid: MadAid; size: csize): ptr MifareClassicSectorNumber {.
    cdecl, importc: "mifare_application_alloc", dynlib: freefareLib.}
proc mifare_application_read*(tag: FreefareTag; mad: Mad; aid: MadAid; buf: pointer;
                             nbytes: csize; key: MifareClassicKey;
                             key_type: MifareClassicKeyType): int32 {.cdecl,
    importc: "mifare_application_read", dynlib: freefareLib.}
proc mifare_application_write*(tag: FreefareTag; mad: Mad; aid: MadAid; buf: pointer;
                              nbytes: csize; key: MifareClassicKey;
                              key_type: MifareClassicKeyType): int32 {.cdecl,
    importc: "mifare_application_write", dynlib: freefareLib.}
proc mifare_application_free*(mad: Mad; aid: MadAid): cint {.cdecl,
    importc: "mifare_application_free", dynlib: freefareLib.}
proc mifare_application_find*(mad: Mad; aid: MadAid): ptr MifareClassicSectorNumber {.
    cdecl, importc: "mifare_application_find", dynlib: freefareLib.}
proc mifare_desfire_taste*(device: ptr device; target: target): bool {.cdecl,
    importc: "mifare_desfire_taste", dynlib: freefareLib.}
##  File types

type
  mifare_desfire_file_types* {.size: sizeof(cint).} = enum
    MDFT_STANDARD_DATA_FILE = 0x00000000, MDFT_BACKUP_DATA_FILE = 0x00000001,
    MDFT_VALUE_FILE_WITH_BACKUP = 0x00000002,
    MDFT_LINEAR_RECORD_FILE_WITH_BACKUP = 0x00000003,
    MDFT_CYCLIC_RECORD_FILE_WITH_BACKUP = 0x00000004


##  Communication mode

const
  MDCM_PLAIN* = 0x00000000
  MDCM_MACED* = 0x00000001
  MDCM_ENCIPHERED* = 0x00000003

##  Mifare DESFire master key settings
## bit 7 - 4: Always 0.
## bit 3: PICC master key settings frozen = 0 (WARNING - this is irreversible); PICC master key settings changeable when authenticated with PICC master key = 1
## bit 2: PICC master key authentication required for creating or deleting applications = 0; Authentication not required = 1
## bit 1: PICC master key authentication required for listing of applications or reading key settings = 0; Free listing of applications and reading key settings = 1
## bit 0: PICC master key frozen (reversible with configuration change or when formatting card) = 0; PICC master key changeable = 1
##

template MDMK_SETTINGS*(picc_master_key_settings_changeable,
                       free_create_delete_application,
                       free_listing_apps_and_key_settings,
                       picc_master_key_changeable: untyped): untyped =
  ((picc_master_key_settings_changeable shl 3) or
      (free_create_delete_application shl 2) or
      (free_listing_apps_and_key_settings shl 1) or (picc_master_key_changeable))

##  Mifare DESFire EV1 Application crypto operations

const
  APPLICATION_CRYPTO_DES* = 0x00000000
  APPLICATION_CRYPTO_3K3DES* = 0x00000040
  APPLICATION_CRYPTO_AES* = 0x00000080

##  Mifare DESFire Application settings
##  bit 7 - 4: Number of key needed to change application keys (key 0 - 13; 0 = master key; 14 = key itself required for key change; 15 = all keys are frozen)
##  bit 3: Application configuration frozen = 0; Application configuration changeable when authenticated with application master key = 1
##  bit 2: Application master key authentication required for create/delete files = 0; Authentication not required = 1
##  bit 1: GetFileIDs, GetFileSettings and GetKeySettings behavior: Master key authentication required = 0; No authentication required = 1
##  bit 0 = Application master key frozen = 0; Application master key changeable = 1
##

template MDAPP_SETTINGS*(key_no_for_key_changing, config_changeable,
                        free_create_delete_files, free_listing_contents,
                        app_master_key_changeable: untyped): untyped =
  ((key_no_for_key_changing shl 4) or (config_changeable shl 3) or
      (free_create_delete_files shl 2) or (free_listing_contents shl 1) or
      (app_master_key_changeable))

##  Access right

template MDAR*(read, write, read_write, change_access_rights: untyped): untyped =
  ((read shl 12) or (write shl 8) or (read_write shl 4) or (change_access_rights))

template MDAR_READ*(ar: untyped): untyped =
  (((ar) shr 12) and 0x0000000F)

template MDAR_WRITE*(ar: untyped): untyped =
  (((ar) shr 8) and 0x0000000F)

template MDAR_READ_WRITE*(ar: untyped): untyped =
  (((ar) shr 4) and 0x0000000F)

template MDAR_CHANGE_AR*(ar: untyped): untyped =
  ((ar) and 0x0000000F)

const
  MDAR_KEY0* = 0x00000000
  MDAR_KEY1* = 0x00000001
  MDAR_KEY2* = 0x00000002
  MDAR_KEY3* = 0x00000003
  MDAR_KEY4* = 0x00000004
  MDAR_KEY5* = 0x00000005
  MDAR_KEY6* = 0x00000006
  MDAR_KEY7* = 0x00000007
  MDAR_KEY8* = 0x00000008
  MDAR_KEY9* = 0x00000009
  MDAR_KEY10* = 0x0000000A
  MDAR_KEY11* = 0x0000000B
  MDAR_KEY12* = 0x0000000C
  MDAR_KEY13* = 0x0000000D
  MDAR_FREE* = 0x0000000E
  MDAR_DENY* = 0x0000000F

##  Status and error codes

const
  OPERATION_OK* = 0x00000000
  NO_CHANGES* = 0x0000000C
  OUT_OF_EEPROM_ERROR* = 0x0000000E
  ILLEGAL_COMMAND_CODE* = 0x0000001C
  INTEGRITY_ERROR* = 0x0000001E
  NO_SUCH_KEY* = 0x00000040
  LENGTH_ERROR* = 0x0000007E
  PERMISSION_ERROR* = 0x0000009D
  PARAMETER_ERROR* = 0x0000009E
  APPLICATION_NOT_FOUND* = 0x000000A0
  APPL_INTEGRITY_ERROR* = 0x000000A1
  AUTHENTICATION_ERROR* = 0x000000AE
  ADDITIONAL_FRAME* = 0x000000AF
  BOUNDARY_ERROR* = 0x000000BE
  PICC_INTEGRITY_ERROR* = 0x000000C1
  COMMAND_ABORTED* = 0x000000CA
  PICC_DISABLED_ERROR* = 0x000000CD
  COUNT_ERROR* = 0x000000CE
  DUPLICATE_ERROR* = 0x000000DE
  EEPROM_ERROR* = 0x000000EE
  FILE_NOT_FOUND* = 0x000000F0
  FILE_INTEGRITY_ERROR* = 0x000000F1

##  Error code managed by the library

const
  CRYPTO_ERROR* = 0x00000001
  TAG_INFO_MISSING_ERROR* = 0x000000BA
  UNKNOWN_TAG_TYPE_ERROR* = 0x000000BB

type
  mifare_desfire_aid* {.importc: "struct mifare_desfire_aid",
                       header: freefareHeader, bycopy.} = object

  MifareDESFireAID* = ptr mifare_desfire_aid
  mifare_desfire_df* {.importc: "struct mifare_desfire_df", header: freefareHeader,
                      bycopy.} = object
    aid* {.importc: "aid".}: uint32
    fid* {.importc: "fid".}: uint16
    df_name* {.importc: "df_name".}: array[16, uint8]
    df_name_len* {.importc: "df_name_len".}: csize

  MifareDESFireDF* = mifare_desfire_df

proc mifare_desfire_aid_new*(aid: uint32): MifareDESFireAID {.cdecl,
    importc: "mifare_desfire_aid_new", dynlib: freefareLib.}
proc mifare_desfire_aid_new_with_mad_aid*(mad_aid: MadAid; n: uint8): MifareDESFireAID {.
    cdecl, importc: "mifare_desfire_aid_new_with_mad_aid", dynlib: freefareLib.}
proc mifare_desfire_aid_get_aid*(aid: MifareDESFireAID): uint32 {.cdecl,
    importc: "mifare_desfire_aid_get_aid", dynlib: freefareLib.}
proc mifare_desfire_last_pcd_error*(tag: FreefareTag): uint8 {.cdecl,
    importc: "mifare_desfire_last_pcd_error", dynlib: freefareLib.}
proc mifare_desfire_last_picc_error*(tag: FreefareTag): uint8 {.cdecl,
    importc: "mifare_desfire_last_picc_error", dynlib: freefareLib.}
type
  INNER_C_STRUCT_freefare_420* {.importc: "struct no_name", header: freefareHeader,
                                bycopy.} = object
    vendor_id* {.importc: "vendor_id".}: uint8
    `type`* {.importc: "type".}: uint8
    subtype* {.importc: "subtype".}: uint8
    version_major* {.importc: "version_major".}: uint8
    version_minor* {.importc: "version_minor".}: uint8
    storage_size* {.importc: "storage_size".}: uint8
    protocol* {.importc: "protocol".}: uint8

  INNER_C_STRUCT_freefare_429* {.importc: "struct no_name", header: freefareHeader,
                                bycopy.} = object
    vendor_id* {.importc: "vendor_id".}: uint8
    `type`* {.importc: "type".}: uint8
    subtype* {.importc: "subtype".}: uint8
    version_major* {.importc: "version_major".}: uint8
    version_minor* {.importc: "version_minor".}: uint8
    storage_size* {.importc: "storage_size".}: uint8
    protocol* {.importc: "protocol".}: uint8

  mifare_desfire_version_info* {.importc: "struct mifare_desfire_version_info",
                                header: freefareHeader, bycopy.} = object
    hardware* {.importc: "hardware".}: INNER_C_STRUCT_freefare_420
    software* {.importc: "software".}: INNER_C_STRUCT_freefare_429
    uid* {.importc: "uid".}: array[7, uint8]
    batch_number* {.importc: "batch_number".}: array[5, uint8]
    production_week* {.importc: "production_week".}: uint8
    production_year* {.importc: "production_year".}: uint8

  INNER_C_STRUCT_freefare_450* {.importc: "struct no_name", header: freefareHeader,
                                bycopy.} = object
    file_size* {.importc: "file_size".}: uint32

  INNER_C_STRUCT_freefare_453* {.importc: "struct no_name", header: freefareHeader,
                                bycopy.} = object
    lower_limit* {.importc: "lower_limit".}: int32
    upper_limit* {.importc: "upper_limit".}: int32
    limited_credit_value* {.importc: "limited_credit_value".}: int32
    limited_credit_enabled* {.importc: "limited_credit_enabled".}: uint8

  INNER_C_STRUCT_freefare_459* {.importc: "struct no_name", header: freefareHeader,
                                bycopy.} = object
    record_size* {.importc: "record_size".}: uint32
    max_number_of_records* {.importc: "max_number_of_records".}: uint32
    current_number_of_records* {.importc: "current_number_of_records".}: uint32

  INNER_C_UNION_freefare_449* {.importc: "struct no_name", header: freefareHeader,
                               bycopy.} = object {.union.}
    standard_file* {.importc: "standard_file".}: INNER_C_STRUCT_freefare_450
    value_file* {.importc: "value_file".}: INNER_C_STRUCT_freefare_453
    linear_record_file* {.importc: "linear_record_file".}: INNER_C_STRUCT_freefare_459

  mifare_desfire_file_settings* {.importc: "struct mifare_desfire_file_settings",
                                 header: freefareHeader, bycopy.} = object
    file_type* {.importc: "file_type".}: uint8
    communication_settings* {.importc: "communication_settings".}: uint8
    access_rights* {.importc: "access_rights".}: uint16
    settings* {.importc: "settings".}: INNER_C_UNION_freefare_449


proc mifare_desfire_tag_new*(device: ptr device; target: target): FreefareTag {.cdecl,
    importc: "mifare_desfire_tag_new", dynlib: freefareLib.}
proc mifare_desfire_tag_free*(tags: FreefareTag) {.cdecl,
    importc: "mifare_desfire_tag_free", dynlib: freefareLib.}
proc mifare_desfire_connect*(tag: FreefareTag): cint {.cdecl,
    importc: "mifare_desfire_connect", dynlib: freefareLib.}
proc mifare_desfire_disconnect*(tag: FreefareTag): cint {.cdecl,
    importc: "mifare_desfire_disconnect", dynlib: freefareLib.}
proc mifare_desfire_authenticate*(tag: FreefareTag; key_no: uint8;
                                 key: MifareDESFireKey): cint {.cdecl,
    importc: "mifare_desfire_authenticate", dynlib: freefareLib.}
proc mifare_desfire_authenticate_iso*(tag: FreefareTag; key_no: uint8;
                                     key: MifareDESFireKey): cint {.cdecl,
    importc: "mifare_desfire_authenticate_iso", dynlib: freefareLib.}
proc mifare_desfire_authenticate_aes*(tag: FreefareTag; key_no: uint8;
                                     key: MifareDESFireKey): cint {.cdecl,
    importc: "mifare_desfire_authenticate_aes", dynlib: freefareLib.}
proc mifare_desfire_change_key_settings*(tag: FreefareTag; settings: uint8): cint {.
    cdecl, importc: "mifare_desfire_change_key_settings", dynlib: freefareLib.}
proc mifare_desfire_get_key_settings*(tag: FreefareTag; settings: ptr uint8;
                                     max_keys: ptr uint8): cint {.cdecl,
    importc: "mifare_desfire_get_key_settings", dynlib: freefareLib.}
proc mifare_desfire_change_key*(tag: FreefareTag; key_no: uint8;
                               new_key: MifareDESFireKey;
                               old_key: MifareDESFireKey): cint {.cdecl,
    importc: "mifare_desfire_change_key", dynlib: freefareLib.}
proc mifare_desfire_get_key_version*(tag: FreefareTag; key_no: uint8;
                                    version: ptr uint8): cint {.cdecl,
    importc: "mifare_desfire_get_key_version", dynlib: freefareLib.}
proc mifare_desfire_create_application*(tag: FreefareTag; aid: MifareDESFireAID;
                                       settings: uint8; key_no: uint8): cint {.cdecl,
    importc: "mifare_desfire_create_application", dynlib: freefareLib.}
proc mifare_desfire_create_application_3k3des*(tag: FreefareTag;
    aid: MifareDESFireAID; settings: uint8; key_no: uint8): cint {.cdecl,
    importc: "mifare_desfire_create_application_3k3des", dynlib: freefareLib.}
proc mifare_desfire_create_application_aes*(tag: FreefareTag;
    aid: MifareDESFireAID; settings: uint8; key_no: uint8): cint {.cdecl,
    importc: "mifare_desfire_create_application_aes", dynlib: freefareLib.}
proc mifare_desfire_create_application_iso*(tag: FreefareTag;
    aid: MifareDESFireAID; settings: uint8; key_no: uint8;
    want_iso_file_identifiers: cint; iso_file_id: uint16; iso_file_name: ptr uint8;
    iso_file_name_len: csize): cint {.cdecl, importc: "mifare_desfire_create_application_iso",
                                   dynlib: freefareLib.}
proc mifare_desfire_create_application_3k3des_iso*(tag: FreefareTag;
    aid: MifareDESFireAID; settings: uint8; key_no: uint8;
    want_iso_file_identifiers: cint; iso_file_id: uint16; iso_file_name: ptr uint8;
    iso_file_name_len: csize): cint {.cdecl, importc: "mifare_desfire_create_application_3k3des_iso",
                                   dynlib: freefareLib.}
proc mifare_desfire_create_application_aes_iso*(tag: FreefareTag;
    aid: MifareDESFireAID; settings: uint8; key_no: uint8;
    want_iso_file_identifiers: cint; iso_file_id: uint16; iso_file_name: ptr uint8;
    iso_file_name_len: csize): cint {.cdecl, importc: "mifare_desfire_create_application_aes_iso",
                                   dynlib: freefareLib.}
proc mifare_desfire_delete_application*(tag: FreefareTag; aid: MifareDESFireAID): cint {.
    cdecl, importc: "mifare_desfire_delete_application", dynlib: freefareLib.}
proc mifare_desfire_get_application_ids*(tag: FreefareTag;
                                        aids: ptr ptr MifareDESFireAID;
                                        count: ptr csize): cint {.cdecl,
    importc: "mifare_desfire_get_application_ids", dynlib: freefareLib.}
proc mifare_desfire_get_df_names*(tag: FreefareTag; dfs: ptr ptr MifareDESFireDF;
                                 count: ptr csize): cint {.cdecl,
    importc: "mifare_desfire_get_df_names", dynlib: freefareLib.}
proc mifare_desfire_free_application_ids*(aids: ptr MifareDESFireAID) {.cdecl,
    importc: "mifare_desfire_free_application_ids", dynlib: freefareLib.}
proc mifare_desfire_select_application*(tag: FreefareTag; aid: MifareDESFireAID): cint {.
    cdecl, importc: "mifare_desfire_select_application", dynlib: freefareLib.}
proc mifare_desfire_format_picc*(tag: FreefareTag): cint {.cdecl,
    importc: "mifare_desfire_format_picc", dynlib: freefareLib.}
proc mifare_desfire_get_version*(tag: FreefareTag;
                                version_info: ptr mifare_desfire_version_info): cint {.
    cdecl, importc: "mifare_desfire_get_version", dynlib: freefareLib.}
proc mifare_desfire_free_mem*(tag: FreefareTag; size: ptr uint32): cint {.cdecl,
    importc: "mifare_desfire_free_mem", dynlib: freefareLib.}
proc mifare_desfire_set_configuration*(tag: FreefareTag; disable_format: bool;
                                      enable_random_uid: bool): cint {.cdecl,
    importc: "mifare_desfire_set_configuration", dynlib: freefareLib.}
proc mifare_desfire_set_default_key*(tag: FreefareTag; key: MifareDESFireKey): cint {.
    cdecl, importc: "mifare_desfire_set_default_key", dynlib: freefareLib.}
proc mifare_desfire_set_ats*(tag: FreefareTag; ats: ptr uint8): cint {.cdecl,
    importc: "mifare_desfire_set_ats", dynlib: freefareLib.}
proc mifare_desfire_get_card_uid*(tag: FreefareTag; uid: cstringArray): cint {.cdecl,
    importc: "mifare_desfire_get_card_uid", dynlib: freefareLib.}
proc mifare_desfire_get_card_uid_raw*(tag: FreefareTag; uid: array[7, uint8]): cint {.
    cdecl, importc: "mifare_desfire_get_card_uid_raw", dynlib: freefareLib.}
proc mifare_desfire_get_file_ids*(tag: FreefareTag; files: ptr ptr uint8;
                                 count: ptr csize): cint {.cdecl,
    importc: "mifare_desfire_get_file_ids", dynlib: freefareLib.}
proc mifare_desfire_get_iso_file_ids*(tag: FreefareTag; files: ptr ptr uint16;
                                     count: ptr csize): cint {.cdecl,
    importc: "mifare_desfire_get_iso_file_ids", dynlib: freefareLib.}
proc mifare_desfire_get_file_settings*(tag: FreefareTag; file_no: uint8; settings: ptr mifare_desfire_file_settings): cint {.
    cdecl, importc: "mifare_desfire_get_file_settings", dynlib: freefareLib.}
proc mifare_desfire_change_file_settings*(tag: FreefareTag; file_no: uint8;
    communication_settings: uint8; access_rights: uint16): cint {.cdecl,
    importc: "mifare_desfire_change_file_settings", dynlib: freefareLib.}
proc mifare_desfire_create_std_data_file*(tag: FreefareTag; file_no: uint8;
    communication_settings: uint8; access_rights: uint16; file_size: uint32): cint {.
    cdecl, importc: "mifare_desfire_create_std_data_file", dynlib: freefareLib.}
proc mifare_desfire_create_std_data_file_iso*(tag: FreefareTag; file_no: uint8;
    communication_settings: uint8; access_rights: uint16; file_size: uint32;
    iso_file_id: uint16): cint {.cdecl, importc: "mifare_desfire_create_std_data_file_iso",
                              dynlib: freefareLib.}
proc mifare_desfire_create_backup_data_file*(tag: FreefareTag; file_no: uint8;
    communication_settings: uint8; access_rights: uint16; file_size: uint32): cint {.
    cdecl, importc: "mifare_desfire_create_backup_data_file", dynlib: freefareLib.}
proc mifare_desfire_create_backup_data_file_iso*(tag: FreefareTag; file_no: uint8;
    communication_settings: uint8; access_rights: uint16; file_size: uint32;
    iso_file_id: uint16): cint {.cdecl, importc: "mifare_desfire_create_backup_data_file_iso",
                              dynlib: freefareLib.}
proc mifare_desfire_create_value_file*(tag: FreefareTag; file_no: uint8;
                                      communication_settings: uint8;
                                      access_rights: uint16; lower_limit: int32;
                                      upper_limit: int32; value: int32;
                                      limited_credit_enable: uint8): cint {.cdecl,
    importc: "mifare_desfire_create_value_file", dynlib: freefareLib.}
proc mifare_desfire_create_linear_record_file*(tag: FreefareTag; file_no: uint8;
    communication_settings: uint8; access_rights: uint16; record_size: uint32;
    max_number_of_records: uint32): cint {.cdecl, importc: "mifare_desfire_create_linear_record_file",
                                        dynlib: freefareLib.}
proc mifare_desfire_create_linear_record_file_iso*(tag: FreefareTag;
    file_no: uint8; communication_settings: uint8; access_rights: uint16;
    record_size: uint32; max_number_of_records: uint32; iso_file_id: uint16): cint {.
    cdecl, importc: "mifare_desfire_create_linear_record_file_iso",
    dynlib: freefareLib.}
proc mifare_desfire_create_cyclic_record_file*(tag: FreefareTag; file_no: uint8;
    communication_settings: uint8; access_rights: uint16; record_size: uint32;
    max_number_of_records: uint32): cint {.cdecl, importc: "mifare_desfire_create_cyclic_record_file",
                                        dynlib: freefareLib.}
proc mifare_desfire_create_cyclic_record_file_iso*(tag: FreefareTag;
    file_no: uint8; communication_settings: uint8; access_rights: uint16;
    record_size: uint32; max_number_of_records: uint32; iso_file_id: uint16): cint {.
    cdecl, importc: "mifare_desfire_create_cyclic_record_file_iso",
    dynlib: freefareLib.}
proc mifare_desfire_delete_file*(tag: FreefareTag; file_no: uint8): cint {.cdecl,
    importc: "mifare_desfire_delete_file", dynlib: freefareLib.}
proc mifare_desfire_read_data*(tag: FreefareTag; file_no: uint8; offset: uint32;
                              length: csize; data: pointer): int32 {.cdecl,
    importc: "mifare_desfire_read_data", dynlib: freefareLib.}
proc mifare_desfire_read_data_ex*(tag: FreefareTag; file_no: uint8; offset: uint32;
                                 length: csize; data: pointer; cs: cint): int32 {.
    cdecl, importc: "mifare_desfire_read_data_ex", dynlib: freefareLib.}
proc mifare_desfire_write_data*(tag: FreefareTag; file_no: uint8; offset: uint32;
                               length: csize; data: pointer): int32 {.cdecl,
    importc: "mifare_desfire_write_data", dynlib: freefareLib.}
proc mifare_desfire_write_data_ex*(tag: FreefareTag; file_no: uint8; offset: uint32;
                                  length: csize; data: pointer; cs: cint): int32 {.
    cdecl, importc: "mifare_desfire_write_data_ex", dynlib: freefareLib.}
proc mifare_desfire_get_value*(tag: FreefareTag; file_no: uint8; value: ptr int32): cint {.
    cdecl, importc: "mifare_desfire_get_value", dynlib: freefareLib.}
proc mifare_desfire_get_value_ex*(tag: FreefareTag; file_no: uint8; value: ptr int32;
                                 cs: cint): cint {.cdecl,
    importc: "mifare_desfire_get_value_ex", dynlib: freefareLib.}
proc mifare_desfire_credit*(tag: FreefareTag; file_no: uint8; amount: int32): cint {.
    cdecl, importc: "mifare_desfire_credit", dynlib: freefareLib.}
proc mifare_desfire_credit_ex*(tag: FreefareTag; file_no: uint8; amount: int32;
                              cs: cint): cint {.cdecl,
    importc: "mifare_desfire_credit_ex", dynlib: freefareLib.}
proc mifare_desfire_debit*(tag: FreefareTag; file_no: uint8; amount: int32): cint {.
    cdecl, importc: "mifare_desfire_debit", dynlib: freefareLib.}
proc mifare_desfire_debit_ex*(tag: FreefareTag; file_no: uint8; amount: int32; cs: cint): cint {.
    cdecl, importc: "mifare_desfire_debit_ex", dynlib: freefareLib.}
proc mifare_desfire_limited_credit*(tag: FreefareTag; file_no: uint8; amount: int32): cint {.
    cdecl, importc: "mifare_desfire_limited_credit", dynlib: freefareLib.}
proc mifare_desfire_limited_credit_ex*(tag: FreefareTag; file_no: uint8;
                                      amount: int32; cs: cint): cint {.cdecl,
    importc: "mifare_desfire_limited_credit_ex", dynlib: freefareLib.}
proc mifare_desfire_write_record*(tag: FreefareTag; file_no: uint8; offset: uint32;
                                 length: csize; data: pointer): int32 {.cdecl,
    importc: "mifare_desfire_write_record", dynlib: freefareLib.}
proc mifare_desfire_write_record_ex*(tag: FreefareTag; file_no: uint8;
                                    offset: uint32; length: csize; data: pointer;
                                    cs: cint): int32 {.cdecl,
    importc: "mifare_desfire_write_record_ex", dynlib: freefareLib.}
proc mifare_desfire_read_records*(tag: FreefareTag; file_no: uint8; offset: uint32;
                                 length: csize; data: pointer): int32 {.cdecl,
    importc: "mifare_desfire_read_records", dynlib: freefareLib.}
proc mifare_desfire_read_records_ex*(tag: FreefareTag; file_no: uint8;
                                    offset: uint32; length: csize; data: pointer;
                                    cs: cint): int32 {.cdecl,
    importc: "mifare_desfire_read_records_ex", dynlib: freefareLib.}
proc mifare_desfire_clear_record_file*(tag: FreefareTag; file_no: uint8): cint {.
    cdecl, importc: "mifare_desfire_clear_record_file", dynlib: freefareLib.}
proc mifare_desfire_commit_transaction*(tag: FreefareTag): cint {.cdecl,
    importc: "mifare_desfire_commit_transaction", dynlib: freefareLib.}
proc mifare_desfire_abort_transaction*(tag: FreefareTag): cint {.cdecl,
    importc: "mifare_desfire_abort_transaction", dynlib: freefareLib.}
proc mifare_desfire_des_key_new*(value: array[8, uint8]): MifareDESFireKey {.cdecl,
    importc: "mifare_desfire_des_key_new", dynlib: freefareLib.}
proc mifare_desfire_3des_key_new*(value: array[16, uint8]): MifareDESFireKey {.cdecl,
    importc: "mifare_desfire_3des_key_new", dynlib: freefareLib.}
proc mifare_desfire_des_key_new_with_version*(value: array[8, uint8]): MifareDESFireKey {.
    cdecl, importc: "mifare_desfire_des_key_new_with_version", dynlib: freefareLib.}
proc mifare_desfire_3des_key_new_with_version*(value: array[16, uint8]): MifareDESFireKey {.
    cdecl, importc: "mifare_desfire_3des_key_new_with_version", dynlib: freefareLib.}
proc mifare_desfire_3k3des_key_new*(value: array[24, uint8]): MifareDESFireKey {.
    cdecl, importc: "mifare_desfire_3k3des_key_new", dynlib: freefareLib.}
proc mifare_desfire_3k3des_key_new_with_version*(value: array[24, uint8]): MifareDESFireKey {.
    cdecl, importc: "mifare_desfire_3k3des_key_new_with_version",
    dynlib: freefareLib.}
proc mifare_desfire_aes_key_new*(value: array[16, uint8]): MifareDESFireKey {.cdecl,
    importc: "mifare_desfire_aes_key_new", dynlib: freefareLib.}
proc mifare_desfire_aes_key_new_with_version*(value: array[16, uint8];
    version: uint8): MifareDESFireKey {.cdecl, importc: "mifare_desfire_aes_key_new_with_version",
                                     dynlib: freefareLib.}
proc mifare_desfire_key_get_version*(key: MifareDESFireKey): uint8 {.cdecl,
    importc: "mifare_desfire_key_get_version", dynlib: freefareLib.}
proc mifare_desfire_key_set_version*(key: MifareDESFireKey; version: uint8) {.cdecl,
    importc: "mifare_desfire_key_set_version", dynlib: freefareLib.}
proc mifare_desfire_key_free*(key: MifareDESFireKey) {.cdecl,
    importc: "mifare_desfire_key_free", dynlib: freefareLib.}
proc tlv_encode*(`type`: uint8; istream: ptr uint8; isize: uint16; osize: ptr csize): ptr uint8 {.
    cdecl, importc: "tlv_encode", dynlib: freefareLib.}
proc tlv_decode*(istream: ptr uint8; `type`: ptr uint8; size: ptr uint16): ptr uint8 {.
    cdecl, importc: "tlv_decode", dynlib: freefareLib.}
proc tlv_record_length*(istream: ptr uint8; field_length_size: ptr csize;
                       field_value_size: ptr csize): csize {.cdecl,
    importc: "tlv_record_length", dynlib: freefareLib.}
proc tlv_append*(a: ptr uint8; b: ptr uint8): ptr uint8 {.cdecl, importc: "tlv_append",
    dynlib: freefareLib.}
type
  MifareKeyType* {.size: sizeof(cint).} = enum
    MIFARE_KEY_DES, MIFARE_KEY_2K3DES, MIFARE_KEY_3K3DES, MIFARE_KEY_AES128

const
  MIFARE_KEY_LAST = MIFARE_KEY_AES128

type
  mifare_key_deriver* {.importc: "struct mifare_key_deriver",
                       header: freefareHeader, bycopy.} = object

  MifareKeyDeriver* = ptr mifare_key_deriver

proc mifare_key_deriver_new_an10922*(master_key: MifareDESFireKey;
                                    output_key_type: MifareKeyType): MifareKeyDeriver {.
    cdecl, importc: "mifare_key_deriver_new_an10922", dynlib: freefareLib.}
proc mifare_key_deriver_begin*(deriver: MifareKeyDeriver): cint {.cdecl,
    importc: "mifare_key_deriver_begin", dynlib: freefareLib.}
proc mifare_key_deriver_update_data*(deriver: MifareKeyDeriver; data: ptr uint8;
                                    len: csize): cint {.cdecl,
    importc: "mifare_key_deriver_update_data", dynlib: freefareLib.}
proc mifare_key_deriver_update_uid*(deriver: MifareKeyDeriver; tag: FreefareTag): cint {.
    cdecl, importc: "mifare_key_deriver_update_uid", dynlib: freefareLib.}
proc mifare_key_deriver_update_aid*(deriver: MifareKeyDeriver;
                                   aid: MifareDESFireAID): cint {.cdecl,
    importc: "mifare_key_deriver_update_aid", dynlib: freefareLib.}
proc mifare_key_deriver_update_cstr*(deriver: MifareKeyDeriver; cstr: cstring): cint {.
    cdecl, importc: "mifare_key_deriver_update_cstr", dynlib: freefareLib.}
proc mifare_key_deriver_end*(deriver: MifareKeyDeriver): MifareDESFireKey {.cdecl,
    importc: "mifare_key_deriver_end", dynlib: freefareLib.}
proc mifare_key_deriver_end_raw*(deriver: MifareKeyDeriver;
                                diversified_bytes: ptr uint8; data_max_len: csize): cint {.
    cdecl, importc: "mifare_key_deriver_end_raw", dynlib: freefareLib.}
proc mifare_key_deriver_free*(state: MifareKeyDeriver) {.cdecl,
    importc: "mifare_key_deriver_free", dynlib: freefareLib.}