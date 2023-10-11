import argparse

import cv2
import numpy as np
from tqdm import tqdm
from ultralytics import YOLO

import supervision as sv


ZONE_POLYGON = np.array([[640, 860], [640, 420], [1280, 420], [1280, 860]])


class VideoProcessor:
    def __init__(
        self,
        source_weights_path: str,
        source_video_path: str,
        target_video_path: str = None,
        confidence_threshold: float = 0.3,
        iou_threshold: float = 0.7,
    ) -> None:
        self.conf_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.source_video_path = source_video_path
        self.target_video_path = target_video_path

        self.model = YOLO(source_weights_path)

        self.tracker = sv.ByteTrack()
        self.video_info = sv.VideoInfo.from_video_path(source_video_path)
        frame_generator = sv.get_video_frames_generator(
            source_path=self.source_video_path)
        self.frame_generator = tqdm(frame_generator, total=self.video_info.total_frames)
        self.ellipse_annotator = sv.EllipseAnnotator()
        self.trace_annotator = sv.TraceAnnotator()
        self.label_annotator = sv.LabelAnnotator(
            text_position=sv.Position.BOTTOM_CENTER)
        self.zone = sv.PolygonZone(
            polygon=ZONE_POLYGON,
            frame_resolution_wh=self.video_info.resolution_wh,
            triggering_position=sv.Position.BOTTOM_CENTER,
        )

    def process_video(self):
        print(self.video_info)
        if self.target_video_path:
            with sv.VideoSink(self.target_video_path, self.video_info) as sink:
                for frame in self.frame_generator:
                    annotated_frame = self.process_frame(frame)
                    sink.write_frame(annotated_frame)
        else:
            for frame in self.frame_generator:
                annotated_frame = self.process_frame(frame)
                cv2.imshow("Processed Video", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            cv2.destroyAllWindows()

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        results = self.model(
            frame, verbose=False, conf=self.conf_threshold, iou=self.iou_threshold)[0]
        detections = sv.Detections.from_ultralytics(results)
        detections = detections[detections.class_id == 0]
        detections = self.tracker.update_with_detections(detections=detections)
        return self.annotate_frame(frame, detections)

    def annotate_frame(
        self, frame: np.ndarray, detections: sv.Detections
    ) -> np.ndarray:
        annotated_frame = frame.copy()
        # annotated_frame = sv.draw_polygon(
        #     annotated_frame, self.zone.polygon, sv.Color.red())
        annotated_frame = self.ellipse_annotator.annotate(
            scene=annotated_frame, detections=detections)
        annotated_frame = self.trace_annotator.annotate(
            scene=annotated_frame, detections=detections)
        labels = [f"#{tracker_id}" for tracker_id in detections.tracker_id]
        annotated_frame = self.label_annotator.annotate(
            scene=annotated_frame, detections=detections, labels=labels)
        return annotated_frame


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Time in Zone Analysis with YOLO and ByteTrack"
    )
    parser.add_argument(
        "--source_weights_path",
        default="yolov8x.pt",
        help="Path to the source weights file",
        type=str,
    )
    parser.add_argument(
        "--source_video_path",
        required=True,
        help="Path to the source video file",
        type=str,
    )
    parser.add_argument(
        "--target_video_path",
        default=None,
        help="Path to the target video file (output)",
        type=str,
    )
    parser.add_argument(
        "--confidence_threshold",
        default=0.3,
        help="Confidence threshold for the model",
        type=float,
    )
    parser.add_argument(
        "--iou_threshold", default=0.7, help="IOU threshold for the model", type=float
    )

    args = parser.parse_args()
    processor = VideoProcessor(
        source_weights_path=args.source_weights_path,
        source_video_path=args.source_video_path,
        target_video_path=args.target_video_path,
        confidence_threshold=args.confidence_threshold,
        iou_threshold=args.iou_threshold,
    )
    processor.process_video()
