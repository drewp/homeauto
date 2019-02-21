/*-
 * Free/Libre Near Field Communication (NFC) library
 *
 * Libnfc historical contributors:
 * Copyright (C) 2009      Roel Verdult
 * Copyright (C) 2009-2013 Romuald Conty
 * Copyright (C) 2010-2012 Romain Tartière
 * Copyright (C) 2010-2013 Philippe Teuwen
 * Copyright (C) 2012-2013 Ludovic Rousseau
 * See AUTHORS file for a more comprehensive list of contributors.
 * Additional contributors of this file:
 *
 * This program is free software: you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License as published by the
 * Free Software Foundation, either version 3 of the License, or (at your
 * option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>
 */

#ifdef C2NIM
#define nfcLib "libnfc.so.5.0.1"
#  mangle uint8_t uint8
#  mangle uint32_t uint32
#  prefix nfc_
#  dynlib nfcLib
#  cdecl
#endif

/**
 * @file nfc.h
 * @brief libnfc interface
 *
 * Provide all usefull functions (API) to handle NFC devices.
 */


#  include <sys/time.h>

#  include <stdint.h>
#  include <stdbool.h>


/*-
 * Free/Libre Near Field Communication (NFC) library
 *
 * Libnfc historical contributors:
 * Copyright (C) 2009      Roel Verdult
 * Copyright (C) 2009-2013 Romuald Conty
 * Copyright (C) 2010-2012 Romain Tartière
 * Copyright (C) 2010-2013 Philippe Teuwen
 * Copyright (C) 2012-2013 Ludovic Rousseau
 * See AUTHORS file for a more comprehensive list of contributors.
 * Additional contributors of this file:
 *
 * This program is free software: you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License as published by the
 * Free Software Foundation, either version 3 of the License, or (at your
 * option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>
 */
/**
 * @file nfc-types.h
 * @brief Define NFC types
 */


#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>


#define NFC_BUFSIZE_CONNSTRING 1024


/**
 * NFC context
 */
struct nfc_context;
typedef struct nfc_context nfc_context;

/**
 * NFC device
 */
struct nfc_device;
typedef struct nfc_device nfc_device;

/**
 * NFC device driver
 */
struct nfc_driver;
typedef struct nfc_driver nfc_driver;

/**
 * Connection string
 */
typedef char nfc_connstring[NFC_BUFSIZE_CONNSTRING];

/**
 * Properties
 */
typedef enum {
  /**
   * Default command processing timeout
   * Property value's (duration) unit is ms and 0 means no timeout (infinite).
   * Default value is set by driver layer
   */
  NP_TIMEOUT_COMMAND,
  /**
   * Timeout between ATR_REQ and ATR_RES
   * When the device is in initiator mode, a target is considered as mute if no
   * valid ATR_RES is received within this timeout value.
   * Default value for this property is 103 ms on PN53x based devices.
   */
  NP_TIMEOUT_ATR,
  /**
   * Timeout value to give up reception from the target in case of no answer.
   * Default value for this property is 52 ms).
   */
  NP_TIMEOUT_COM,
  /** Let the PN53X chip handle the CRC bytes. This means that the chip appends
  * the CRC bytes to the frames that are transmitted. It will parse the last
  * bytes from received frames as incoming CRC bytes. They will be verified
  * against the used modulation and protocol. If an frame is expected with
  * incorrect CRC bytes this option should be disabled. Example frames where
  * this is useful are the ATQA and UID+BCC that are transmitted without CRC
  * bytes during the anti-collision phase of the ISO14443-A protocol. */
  NP_HANDLE_CRC,
  /** Parity bits in the network layer of ISO14443-A are by default generated and
   * validated in the PN53X chip. This is a very convenient feature. On certain
   * times though it is useful to get full control of the transmitted data. The
   * proprietary MIFARE Classic protocol uses for example custom (encrypted)
   * parity bits. For interoperability it is required to be completely
   * compatible, including the arbitrary parity bits. When this option is
   * disabled, the functions to communicating bits should be used. */
  NP_HANDLE_PARITY,
  /** This option can be used to enable or disable the electronic field of the
   * NFC device. */
  NP_ACTIVATE_FIELD,
  /** The internal CRYPTO1 co-processor can be used to transmit messages
   * encrypted. This option is automatically activated after a successful MIFARE
   * Classic authentication. */
  NP_ACTIVATE_CRYPTO1,
  /** The default configuration defines that the PN53X chip will try indefinitely
   * to invite a tag in the field to respond. This could be desired when it is
   * certain a tag will enter the field. On the other hand, when this is
   * uncertain, it will block the application. This option could best be compared
   * to the (NON)BLOCKING option used by (socket)network programming. */
  NP_INFINITE_SELECT,
  /** If this option is enabled, frames that carry less than 4 bits are allowed.
   * According to the standards these frames should normally be handles as
   * invalid frames. */
  NP_ACCEPT_INVALID_FRAMES,
  /** If the NFC device should only listen to frames, it could be useful to let
   * it gather multiple frames in a sequence. They will be stored in the internal
   * FIFO of the PN53X chip. This could be retrieved by using the receive data
   * functions. Note that if the chip runs out of bytes (FIFO = 64 bytes long),
   * it will overwrite the first received frames, so quick retrieving of the
   * received data is desirable. */
  NP_ACCEPT_MULTIPLE_FRAMES,
  /** This option can be used to enable or disable the auto-switching mode to
   * ISO14443-4 is device is compliant.
   * In initiator mode, it means that NFC chip will send RATS automatically when
   * select and it will automatically poll for ISO14443-4 card when ISO14443A is
   * requested.
   * In target mode, with a NFC chip compliant (ie. PN532), the chip will
   * emulate a 14443-4 PICC using hardware capability */
  NP_AUTO_ISO14443_4,
  /** Use automatic frames encapsulation and chaining. */
  NP_EASY_FRAMING,
  /** Force the chip to switch in ISO14443-A */
  NP_FORCE_ISO14443_A,
  /** Force the chip to switch in ISO14443-B */
  NP_FORCE_ISO14443_B,
  /** Force the chip to run at 106 kbps */
  NP_FORCE_SPEED_106,
} nfc_property;

// Compiler directive, set struct alignment to 1 uint8_t for compatibility
#  pragma pack(1)

/**
 * @enum nfc_dep_mode
 * @brief NFC D.E.P. (Data Exchange Protocol) active/passive mode
 */
typedef enum {
  NDM_UNDEFINED = 0,
  NDM_PASSIVE,
  NDM_ACTIVE,
} nfc_dep_mode;

/**
 * @struct nfc_dep_info
 * @brief NFC target information in D.E.P. (Data Exchange Protocol) see ISO/IEC 18092 (NFCIP-1)
 */
typedef struct {
  /** NFCID3 */
  uint8_t  abtNFCID3[10];
  /** DID */
  uint8_t  btDID;
  /** Supported send-bit rate */
  uint8_t  btBS;
  /** Supported receive-bit rate */
  uint8_t  btBR;
  /** Timeout value */
  uint8_t  btTO;
  /** PP Parameters */
  uint8_t  btPP;
  /** General Bytes */
  uint8_t  abtGB[48];
  size_t  szGB;
  /** DEP mode */
  nfc_dep_mode ndm;
} nfc_dep_info;

/**
 * @struct nfc_iso14443a_info
 * @brief NFC ISO14443A tag (MIFARE) information
 */
typedef struct {
  uint8_t  abtAtqa[2];
  uint8_t  btSak;
  size_t  szUidLen;
  uint8_t  abtUid[10];
  size_t  szAtsLen;
  uint8_t  abtAts[254]; // Maximal theoretical ATS is FSD-2, FSD=256 for FSDI=8 in RATS
} nfc_iso14443a_info;

/**
 * @struct nfc_felica_info
 * @brief NFC FeLiCa tag information
 */
typedef struct {
  size_t  szLen;
  uint8_t  btResCode;
  uint8_t  abtId[8];
  uint8_t  abtPad[8];
  uint8_t  abtSysCode[2];
} nfc_felica_info;

/**
 * @struct nfc_iso14443b_info
 * @brief NFC ISO14443B tag information
 */
typedef struct {
  /** abtPupi store PUPI contained in ATQB (Answer To reQuest of type B) (see ISO14443-3) */
  uint8_t abtPupi[4];
  /** abtApplicationData store Application Data contained in ATQB (see ISO14443-3) */
  uint8_t abtApplicationData[4];
  /** abtProtocolInfo store Protocol Info contained in ATQB (see ISO14443-3) */
  uint8_t abtProtocolInfo[3];
  /** ui8CardIdentifier store CID (Card Identifier) attributted by PCD to the PICC */
  uint8_t ui8CardIdentifier;
} nfc_iso14443b_info;

/**
 * @struct nfc_iso14443bi_info
 * @brief NFC ISO14443B' tag information
 */
typedef struct {
  /** DIV: 4 LSBytes of tag serial number */
  uint8_t abtDIV[4];
  /** Software version & type of REPGEN */
  uint8_t btVerLog;
  /** Config Byte, present if long REPGEN */
  uint8_t btConfig;
  /** ATR, if any */
  size_t szAtrLen;
  uint8_t  abtAtr[33];
} nfc_iso14443bi_info;

/**
 * @struct nfc_iso14443b2sr_info
 * @brief NFC ISO14443-2B ST SRx tag information
 */
typedef struct {
  uint8_t abtUID[8];
} nfc_iso14443b2sr_info;

/**
 * @struct nfc_iso14443b2ct_info
 * @brief NFC ISO14443-2B ASK CTx tag information
 */
typedef struct {
  uint8_t abtUID[4];
  uint8_t btProdCode;
  uint8_t btFabCode;
} nfc_iso14443b2ct_info;

/**
 * @struct nfc_jewel_info
 * @brief NFC Jewel tag information
 */
typedef struct {
  uint8_t  btSensRes[2];
  uint8_t  btId[4];
} nfc_jewel_info;

/**
 * @union nfc_target_info
 * @brief Union between all kind of tags information structures.
 */
typedef union {
  nfc_iso14443a_info nai;
  nfc_felica_info nfi;
  nfc_iso14443b_info nbi;
  nfc_iso14443bi_info nii;
  nfc_iso14443b2sr_info nsi;
  nfc_iso14443b2ct_info nci;
  nfc_jewel_info nji;
  nfc_dep_info ndi;
} nfc_target_info;

/**
 * @enum nfc_baud_rate
 * @brief NFC baud rate enumeration
 */
typedef enum {
  NBR_UNDEFINED = 0,
  NBR_106,
  NBR_212,
  NBR_424,
  NBR_847,
} nfc_baud_rate;

/**
 * @enum nfc_modulation_type
 * @brief NFC modulation type enumeration
 */
typedef enum {
  NMT_ISO14443A = 1,
  NMT_JEWEL,
  NMT_ISO14443B,
  NMT_ISO14443BI, // pre-ISO14443B aka ISO/IEC 14443 B' or Type B'
  NMT_ISO14443B2SR, // ISO14443-2B ST SRx
  NMT_ISO14443B2CT, // ISO14443-2B ASK CTx
  NMT_FELICA,
  NMT_DEP,
} nfc_modulation_type;

/**
 * @enum nfc_mode
 * @brief NFC mode type enumeration
 */
typedef enum {
  N_TARGET,
  N_INITIATOR,
} nfc_mode;

/**
 * @struct nfc_modulation
 * @brief NFC modulation structure
 */
typedef struct {
  nfc_modulation_type nmt;
  nfc_baud_rate nbr;
} nfc_modulation;

/**
 * @struct nfc_target
 * @brief NFC target structure
 */
typedef struct {
  nfc_target_info nti;
  nfc_modulation nm;
} nfc_target;

// Reset struct alignment to default
#  pragma pack()


/* Library initialization/deinitialization */
void nfc_init(nfc_context **context);
void nfc_exit(nfc_context *context);
int nfc_register_driver(const nfc_driver *driver);

/* NFC Device/Hardware manipulation */
nfc_device *nfc_open(nfc_context *context, const nfc_connstring connstring);
void nfc_close(nfc_device *pnd);
int nfc_abort_command(nfc_device *pnd);
size_t nfc_list_devices(nfc_context *context, nfc_connstring connstrings[], size_t connstrings_len);
int nfc_idle(nfc_device *pnd);

/* NFC initiator: act as "reader" */
int nfc_initiator_init(nfc_device *pnd);
int nfc_initiator_init_secure_element(nfc_device *pnd);
int nfc_initiator_select_passive_target(nfc_device *pnd, const nfc_modulation nm, const uint8_t *pbtInitData, const size_t szInitData, nfc_target *pnt);
int nfc_initiator_list_passive_targets(nfc_device *pnd, const nfc_modulation nm, nfc_target ant[], const size_t szTargets);
int nfc_initiator_poll_target(nfc_device *pnd, const nfc_modulation *pnmTargetTypes, const size_t szTargetTypes, const uint8_t uiPollNr, const uint8_t uiPeriod, nfc_target *pnt);
int nfc_initiator_select_dep_target(nfc_device *pnd, const nfc_dep_mode ndm, const nfc_baud_rate nbr, const nfc_dep_info *pndiInitiator, nfc_target *pnt, const int timeout);
int nfc_initiator_poll_dep_target(nfc_device *pnd, const nfc_dep_mode ndm, const nfc_baud_rate nbr, const nfc_dep_info *pndiInitiator, nfc_target *pnt, const int timeout);
int nfc_initiator_deselect_target(nfc_device *pnd);
int nfc_initiator_transceive_bytes(nfc_device *pnd, const uint8_t *pbtTx, const size_t szTx, uint8_t *pbtRx, const size_t szRx, int timeout);
int nfc_initiator_transceive_bits(nfc_device *pnd, const uint8_t *pbtTx, const size_t szTxBits, const uint8_t *pbtTxPar, uint8_t *pbtRx, const size_t szRx, uint8_t *pbtRxPar);
int nfc_initiator_transceive_bytes_timed(nfc_device *pnd, const uint8_t *pbtTx, const size_t szTx, uint8_t *pbtRx, const size_t szRx, uint32_t *cycles);
int nfc_initiator_transceive_bits_timed(nfc_device *pnd, const uint8_t *pbtTx, const size_t szTxBits, const uint8_t *pbtTxPar, uint8_t *pbtRx, const size_t szRx, uint8_t *pbtRxPar, uint32_t *cycles);
int nfc_initiator_target_is_present(nfc_device *pnd, const nfc_target *pnt);

/* NFC target: act as tag (i.e. MIFARE Classic) or NFC target device. */
int nfc_target_init(nfc_device *pnd, nfc_target *pnt, uint8_t *pbtRx, const size_t szRx, int timeout);
int nfc_target_send_bytes(nfc_device *pnd, const uint8_t *pbtTx, const size_t szTx, int timeout);
int nfc_target_receive_bytes(nfc_device *pnd, uint8_t *pbtRx, const size_t szRx, int timeout);
int nfc_target_send_bits(nfc_device *pnd, const uint8_t *pbtTx, const size_t szTxBits, const uint8_t *pbtTxPar);
int nfc_target_receive_bits(nfc_device *pnd, uint8_t *pbtRx, const size_t szRx, uint8_t *pbtRxPar);

/* Error reporting */
const char *nfc_strerror(const nfc_device *pnd);
int nfc_strerror_r(const nfc_device *pnd, char *buf, size_t buflen);
void nfc_perror(const nfc_device *pnd, const char *s);
int nfc_device_get_last_error(const nfc_device *pnd);

/* Special data accessors */
const char *nfc_device_get_name(nfc_device *pnd);
const char *nfc_device_get_connstring(nfc_device *pnd);
int nfc_device_get_supported_modulation(nfc_device *pnd, const nfc_mode mode,  const nfc_modulation_type **const supported_mt);
int nfc_device_get_supported_baud_rate(nfc_device *pnd, const nfc_modulation_type nmt, const nfc_baud_rate **const supported_br);

/* Properties accessors */
int nfc_device_set_property_int(nfc_device *pnd, const nfc_property property, const int value);
int nfc_device_set_property_bool(nfc_device *pnd, const nfc_property property, const bool bEnable);

/* Misc. functions */
void iso14443a_crc(uint8_t *pbtData, size_t szLen, uint8_t *pbtCrc);
void iso14443a_crc_append(uint8_t *pbtData, size_t szLen);
void iso14443b_crc(uint8_t *pbtData, size_t szLen, uint8_t *pbtCrc);
void iso14443b_crc_append(uint8_t *pbtData, size_t szLen);
uint8_t *iso14443a_locate_historical_bytes(uint8_t *pbtAts, size_t szAts, size_t *pszTk);

void nfc_free(void *p);
const char *nfc_version(void);
int nfc_device_get_information_about(nfc_device *pnd, char **buf);

/* String converter functions */
const char *str_nfc_modulation_type(const nfc_modulation_type nmt);
const char *str_nfc_baud_rate(const nfc_baud_rate nbr);
int str_nfc_target(char **buf, const nfc_target *pnt, bool verbose);

/* Error codes */
/** @ingroup error
 * @hideinitializer
 * Success (no error)
 */
#define NFC_SUCCESS			 0
/** @ingroup error
 * @hideinitializer
 * Input / output error, device may not be usable anymore without re-open it
 */
#define NFC_EIO				-1
/** @ingroup error
 * @hideinitializer
 * Invalid argument(s)
 */
#define NFC_EINVARG			-2
/** @ingroup error
 * @hideinitializer
 *  Operation not supported by device
 */
#define NFC_EDEVNOTSUPP			-3
/** @ingroup error
 * @hideinitializer
 * No such device
 */
#define NFC_ENOTSUCHDEV			-4
/** @ingroup error
 * @hideinitializer
 * Buffer overflow
 */
#define NFC_EOVFLOW			-5
/** @ingroup error
 * @hideinitializer
 * Operation timed out
 */
#define NFC_ETIMEOUT			-6
/** @ingroup error
 * @hideinitializer
 * Operation aborted (by user)
 */
#define NFC_EOPABORTED			-7
/** @ingroup error
 * @hideinitializer
 * Not (yet) implemented
 */
#define NFC_ENOTIMPL			-8
/** @ingroup error
 * @hideinitializer
 * Target released
 */
#define NFC_ETGRELEASED			-10
/** @ingroup error
 * @hideinitializer
 * Error while RF transmission
 */
#define NFC_ERFTRANS			-20
/** @ingroup error
 * @hideinitializer
 * MIFARE Classic: authentication failed
 */
#define NFC_EMFCAUTHFAIL		-30
/** @ingroup error
 * @hideinitializer
 * Software error (allocation, file/pipe creation, etc.)
 */
#define NFC_ESOFT			-80
/** @ingroup error
 * @hideinitializer
 * Device's internal chip error
 */
#define NFC_ECHIP			-90

