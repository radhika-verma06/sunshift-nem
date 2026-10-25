// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Reference registry for unique, evidence-linked P2P energy intervals.
/// @dev Prototype only: not deployed, audited, or connected to the web demo.
contract PeerEnergyRegistry {
    address public immutable owner;
    mapping(address => bool) public reporters;
    mapping(bytes32 => bool) public usedTradeIds;

    event ReporterUpdated(address indexed reporter, bool enabled);
    event PeerEnergyTradeRecorded(
        bytes32 indexed tradeId,
        bytes32 indexed planHash,
        bytes32 meterEvidenceHash,
        bytes32 regionCode,
        address seller,
        address buyer,
        uint64 intervalStart,
        uint64 intervalEnd,
        uint128 energyWh,
        uint64 agreedPriceCentsPerKWh
    );

    error UnauthorizedReporter();
    error InvalidTrade();
    error DuplicateTrade();

    constructor() {
        owner = msg.sender;
        reporters[msg.sender] = true;
    }

    function setReporter(address reporter, bool enabled) external {
        if (msg.sender != owner) revert UnauthorizedReporter();
        if (reporter == address(0)) revert InvalidTrade();
        reporters[reporter] = enabled;
        emit ReporterUpdated(reporter, enabled);
    }

    function recordTrade(
        bytes32 tradeId,
        bytes32 planHash,
        bytes32 meterEvidenceHash,
        bytes32 regionCode,
        address seller,
        address buyer,
        uint64 intervalStart,
        uint64 intervalEnd,
        uint128 energyWh,
        uint64 agreedPriceCentsPerKWh
    ) external {
        if (!reporters[msg.sender]) revert UnauthorizedReporter();
        bytes32 expectedTradeId = keccak256(abi.encode(seller, buyer, regionCode, intervalStart, intervalEnd));
        if (tradeId != expectedTradeId) revert InvalidTrade();
        if (usedTradeIds[tradeId]) revert DuplicateTrade();
        if (
            tradeId == bytes32(0) || planHash == bytes32(0) ||
            meterEvidenceHash == bytes32(0) || regionCode == bytes32(0) ||
            seller == address(0) || buyer == address(0) || seller == buyer ||
            intervalEnd <= intervalStart || energyWh == 0
        ) revert InvalidTrade();

        usedTradeIds[tradeId] = true;
        emit PeerEnergyTradeRecorded(
            tradeId, planHash, meterEvidenceHash, regionCode,
            seller, buyer, intervalStart, intervalEnd, energyWh,
            agreedPriceCentsPerKWh
        );
    }
}
