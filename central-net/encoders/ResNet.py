import torch
import torch.nn as nn
from torchsummary import summary


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(
        self, in_channels, out_channels, stride=1, i_downsample=None, dropout_rate=0
    ):
        super(Bottleneck, self).__init__()

        self.dropout = nn.Dropout(dropout_rate)

        self.conv1 = nn.Conv2d(
            in_channels,
            out_channels=out_channels,
            kernel_size=1,
            stride=stride,
            padding=0,
            bias=False,
        )
        self.batch_norm1 = nn.BatchNorm2d(out_channels)

        self.conv2 = nn.Conv2d(
            out_channels,
            out_channels,
            kernel_size=3,
            stride=stride,
            padding=1,
            bias=False,
        )
        self.batch_norm2 = nn.BatchNorm2d(out_channels)

        self.conv3 = nn.Conv2d(
            out_channels,
            out_channels * self.expansion,
            kernel_size=1,
            stride=1,
            padding=0,
            bias=False,
        )
        self.batch_norm3 = nn.BatchNorm2d(out_channels * self.expansion)

        self.i_downsample = i_downsample
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        identity = x.clone()
        x = self.conv1(x)
        x = self.batch_norm1(x)
        x = self.relu(x)
        x = self.dropout(x)

        x = self.dropout(self.relu(self.batch_norm2(self.conv2(x))))

        x = self.conv3(x)
        x = self.batch_norm3(x)
        x = self.dropout(x)
        # downsample if needed
        if self.i_downsample is not None:
            print("downsample")
            identity = self.i_downsample(identity)
        # add identity
        print(x.shape, identity.shape)

        x += identity
        x = self.relu(x)

        return x


class Block(nn.Module):
    expansion = 1

    def __init__(self, in_channels, out_channels, i_downsample=None, stride=1):
        super(Block, self).__init__()

        self.conv1 = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size=3,
            padding=1,
            stride=stride,
            bias=False,
        )
        self.batch_norm1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(
            out_channels,
            out_channels,
            kernel_size=3,
            padding=1,
            stride=stride,
            bias=False,
        )
        self.batch_norm2 = nn.BatchNorm2d(out_channels)

        self.i_downsample = i_downsample
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        identity = x.clone()

        x = self.relu(self.batch_norm2(self.conv1(x)))

        x = self.batch_norm2(self.conv2(x))

        if self.i_downsample is not None:
            identity = self.i_downsample(identity)
        x += identity
        x = self.relu(x)
        return x


class ResNet(nn.Module):
    def __init__(
        self,
        block,
        layers,
        num_classes,
        dropout_rate=0.0,
        nb_channel=3,
        classifier=None,
    ):
        super(ResNet, self).__init__()
        self.in_channels = 64

        # resnet stem
        self.conv1 = nn.Conv2d(
            # nb_channel, self.in_channels, kernel_size=7, stride=2, padding=3, bias=False
            in_channels=nb_channel,
            out_channels=self.in_channels,
            kernel_size=7,
            stride=2,
            padding=3,
            bias=False,
        )
        self.bn1 = nn.BatchNorm2d(self.in_channels)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)

        # res blocks
        self.layer1 = self._make_layer(
            block=block, out_channels=64, blocks=layers[0], stride=1
        )
        self.layer2 = self._make_layer(
            block=block, out_channels=128, blocks=layers[1], stride=2
        )
        self.layer3 = self._make_layer(
            block=block, out_channels=256, blocks=layers[2], stride=2
        )
        self.layer4 = self._make_layer(
            block=block, out_channels=512, blocks=layers[3], stride=2
        )

        # classifier block
        self.adappool = nn.AdaptiveAvgPool2d((2, 2))
        if classifier is None:
            self.classifier = nn.Linear(512 * block.expansion, num_classes)
        else:
            self.classifier = classifier(512 * block.expansion, num_classes)

    def _make_layer(self, block, out_channels, blocks, stride=1):

        downsample = None

        if stride != 1 or self.in_channels != out_channels * block.expansion:

            downsample = nn.Sequential(
                nn.Conv2d(
                    in_channels=self.in_channels,
                    out_channels=out_channels * block.expansion,
                    kernel_size=1,
                    stride=stride,
                    bias=False,
                ),
                nn.BatchNorm2d(num_features=out_channels * block.expansion),
            )

        layers = []

        layers.append(block(self.in_channels, out_channels, stride, downsample))

        self.in_channels = out_channels * block.expansion

        for i in range(1, blocks):
            layers.append(block(self.in_channels, out_channels))

        return nn.Sequential(*layers)

    def forward(self, x):

        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.adappool(x)
        x = torch.flatten(x, 1)

        return self.classifier(x)


if __name__ == "__main__":
    # resnet50 = ResNet(Bottleneck, layers=[3, 4, 23, 3], num_classes=10)
    resnet50 = ResNet(Bottleneck, layers=[3, 4, 23, 3], num_classes=10)
    resnet34 = ResNet(block=Bottleneck, layers=[3, 4, 6, 3], num_classes=10)
    resnet18 = ResNet(block=Block, layers=[2, 2, 2, 2], num_classes=10)
    summary(resnet50, input_size=(3, 224, 224), device="cpu")
