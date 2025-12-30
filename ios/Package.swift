// swift-tools-version:5.7
import PackageDescription

let package = Package(
    name: "PremierVoice",
    platforms: [
        .iOS(.v14),
        .macOS(.v11)
    ],
    products: [
        .library(
            name: "PremierVoice",
            targets: ["PremierVoice"]),
    ],
    dependencies: [],
    targets: [
        .target(
            name: "PremierVoice",
            dependencies: []),
        .testTarget(
            name: "PremierVoiceTests",
            dependencies: ["PremierVoice"]),
    ]
)
